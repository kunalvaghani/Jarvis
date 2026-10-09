"""Small, live-data and computed answers; no stored changing answers."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import math
from pathlib import Path
import random
import re
import shutil
import socket
import subprocess
import threading
import time

import requests


NUMBER = r"-?\d+(?:\.\d+)?"
WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
         "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
         "nineteen": 19, "twenty": 20}
CURRENCY = {"rupees": "INR", "rupee": "INR", "dollars": "USD", "dollar": "USD",
            "euros": "EUR", "euro": "EUR", "pounds": "GBP", "pound": "GBP"}
UNITS = {"kilometers": ("miles", Decimal("0.621371")),
         "kilometres": ("miles", Decimal("0.621371")),
         "miles": ("kilometers", Decimal("1.609344")),
         "kilograms": ("pounds", Decimal("2.204623")),
         "pounds": ("kilograms", Decimal("0.45359237")),
         "liters": ("milliliters", Decimal("1000")),
         "litres": ("milliliters", Decimal("1000")),
         "inches": ("centimeters", Decimal("2.54")),
         "hours": ("seconds", Decimal("3600")),
         "minutes": ("hours", Decimal(1) / Decimal(60)),
         "months": ("years", Decimal(1) / Decimal(12))}


def number(value):
    value = value.strip().casefold()
    if value in WORDS:
        return Decimal(WORDS[value])
    return Decimal(value)


def say(value):
    value = Decimal(value)
    return format(value.quantize(Decimal("0.01")).normalize(), "f")


class EverydayRuntime:
    def __init__(self, memory=None, weather=None, clock=None, http_get=None, settings=None):
        self.memory = memory
        self.weather = weather
        self.clock = clock or datetime.now
        self.http_get = http_get or requests.get
        self.settings = settings or {}
        self.rates = {}
        self.lock = threading.Lock()

    def profile(self, key):
        source = self.memory.profile_text() if self.memory else ""
        match = re.search(r"(?im)^- " + re.escape(key) + r":\s*([^\n]+)", source)
        return match[1].strip() if match else ""

    def _dates(self, text):
        today = self.clock().date()
        if re.fullmatch(r"(?:what(?: is|'s) )?tomorrow'?s date|what date is tomorrow", text):
            return "Tomorrow is " + (today + timedelta(days=1)).strftime("%A, %d %B %Y") + "."
        if re.fullmatch(r"what date was yesterday|(?:what(?: was|'s) )?yesterday'?s date", text):
            return "Yesterday was " + (today - timedelta(days=1)).strftime("%A, %d %B %Y") + "."
        match = re.fullmatch(r"what date (?:is|was) (\d{1,4}) (days?|weeks?) (from now|ago)", text)
        if match:
            amount = int(match[1]) * (7 if match[2].startswith("week") else 1)
            if amount > 36500:
                return "That date is too far away to calculate here."
            day = today + timedelta(days=amount * (1 if match[3] == "from now" else -1))
            return day.strftime("%A, %d %B %Y") + "."
        if re.fullmatch(r"how many days are left this year", text):
            return f"{(datetime(today.year + 1, 1, 1).date() - today).days} days remain until next year."
        match = re.fullmatch(r"how many hours until (\d{1,2})(?::(\d{2}))? ?(am|pm)", text)
        if match:
            hour = int(match[1]) % 12 + (12 if match[3] == "pm" else 0)
            minute = int(match[2] or 0)
            if minute > 59:
                return "That time is invalid."
            now = self.clock()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target < now:
                target += timedelta(days=1)
            return f"{(target - now).total_seconds() / 3600:.1f} hours until {match[1]} {match[3].upper()}."
        match = re.fullmatch(r"what day falls on ([a-z]+) (\d{1,2})(?: (\d{4}))?", text)
        if match:
            try:
                month = datetime.strptime(match[1], "%B").month
                year = int(match[3]) if match[3] else today.year
                day = today.replace(year=year, month=month, day=int(match[2]))
                if not match[3] and day < today:
                    day = day.replace(year=year + 1)
                return day.strftime("%A, %d %B %Y") + "."
            except ValueError:
                return "That date is invalid."
        if re.fullmatch(r"is this a leap year", text):
            leap = today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0)
            return f"{'Yes' if leap else 'No'}, {today.year} is {'a' if leap else 'not a'} leap year."
        if re.fullmatch(r"is it (monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?: today)?", text):
            return f"{'Yes' if text.split()[2].capitalize() == today.strftime('%A') else 'No'}, today is {today.strftime('%A')}."
        if re.fullmatch(r"how (?:long|many days) until my birthday", text):
            birth = self.profile("Birth date")
            try:
                month_day = datetime.strptime(birth, "%d %B %Y")
                next_day = today.replace(year=today.year, month=month_day.month, day=month_day.day)
                if next_day < today:
                    next_day = next_day.replace(year=today.year + 1)
                days = (next_day - today).days
                return "Your birthday is today." if days == 0 else f"Your birthday is in {days} days, on {next_day.strftime('%d %B %Y')}."
            except ValueError:
                return "I don't have a valid birth date in your Obsidian profile."
        return None

    def _remote_time(self, text):
        if re.fullmatch(r"what is the time difference between india and canada", text):
            return "Canada has several time zones. Name a Canadian city for an accurate current difference."
        conversion = re.fullmatch(r"convert (\d{1,2})(?::(\d{2}))? ?(am|pm) ist to ([a-z][a-z .-]{1,50}) time", text)
        if conversion:
            hour = int(conversion[1]) % 12 + (12 if conversion[3] == "pm" else 0)
            minute = int(conversion[2] or 0)
            if int(conversion[1]) not in range(1, 13) or minute > 59:
                return "That time is invalid."
            city = conversion[4].strip()
            result = self.weather.current(city) if self.weather else None
            offset = result.get("utc_offset_seconds") if result else None
            if not isinstance(offset, (int, float)):
                return f"I couldn't verify the current time offset for {city}."
            source = datetime.combine(self.clock().date(), datetime.min.time(), tzinfo=timezone(timedelta(hours=5, minutes=30)))
            source = source.replace(hour=hour, minute=minute)
            target = source.astimezone(timezone(timedelta(seconds=offset)))
            return f"{conversion[1]} {conversion[3].upper()} IST is {target.strftime('%I:%M %p').lstrip('0')} in {result['city']} on {target.strftime('%d %B')}, using today's offset."
        match = re.fullmatch(r"(?:what time is it(?: right now)? in|time in|tell me the (?:current |local )?time in) ([a-z][a-z ,.-]{1,70})", text)
        if not match:
            return None
        city = match[1].strip()
        if city == "india" and self.profile("Current city"):
            city = self.profile("Current city").split(",")[0]
        result = self.weather.current(city) if self.weather else None
        offset = result.get("utc_offset_seconds") if result else None
        if not isinstance(offset, (int, float)):
            return f"I couldn't verify the current local time in {city}."
        local = datetime.now(timezone.utc) + timedelta(seconds=offset)
        return f"It is {local.strftime('%I:%M %p').lstrip('0')} in {result['city']} (current local offset)."

    def _profile(self, text):
        fields = {
            "what is my name": "Full name", "who am i": "Full name",
            "where am i from": "Hometown", "what is my hometown": "Hometown",
            "where do i live": "Current city", "what city do i live in": "Current city",
            "when is my birthday": "Birth date", "what is my birthday": "Birth date",
            "what is my birth date": "Birth date", "what is my career goal": "Career goal",
            "where do i want to work": "Career goal"}
        field = fields.get(text)
        if field:
            value = self.profile(field)
            return f"Your {field.lower()} is {value}." if value else f"I don't have your {field.lower()} in Obsidian yet."
        if text in {"how old am i", "what is my age"}:
            birth = self.profile("Birth date")
            try:
                born = datetime.strptime(birth, "%d %B %Y").date()
                today = self.clock().date()
                age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
                return f"You are {age} years old today." if age >= 0 else "Your saved birth date is in the future."
            except ValueError:
                return "I don't have a valid birth date in Obsidian."
        return None

    def _math(self, text):
        token = rf"(?:{NUMBER}|{'|'.join(WORDS)})"
        patterns = [
            (rf"(?:what is )?({token}) (?:plus|\+) ({token})", lambda a, b: a + b),
            (rf"(?:what is )?({token}) (?:minus|-) ({token})", lambda a, b: a - b),
            (rf"(?:what is )?({token}) (?:times|multiplied by|\*) ({token})", lambda a, b: a * b),
            (rf"multiply ({token}) by ({token})", lambda a, b: a * b),
            (rf"(?:what is )?({token}) (?:divided by|/) ({token})", lambda a, b: a / b),
            (rf"divide ({token}) by ({token})", lambda a, b: a / b),
        ]
        for pattern, calculation in patterns:
            match = re.fullmatch(pattern, text)
            if match:
                try:
                    a, b = number(match[1]), number(match[2])
                    if b == 0 and ("divid" in text or "/" in text):
                        return "Division by zero is undefined."
                    return f"The result is {say(calculation(a, b))}."
                except (InvalidOperation, ZeroDivisionError):
                    return "I couldn't calculate that."
        match = re.fullmatch(rf"(?:what is )?({token}) squared", text)
        if match:
            return f"The result is {say(number(match[1]) ** 2)}."
        match = re.fullmatch(rf"(?:what is )?the square root of ({token})", text)
        if match:
            value = number(match[1])
            return "A negative number has no real square root." if value < 0 else f"The square root is {say(Decimal(str(math.sqrt(float(value)))))}."
        match = re.fullmatch(rf"(?:what is |how much is )?({token}) percent of ({token})", text)
        if match:
            return f"{say(number(match[1]) * number(match[2]) / 100)}."
        match = re.fullmatch(rf"(?:what is |how much is )?({token}) percent off ({token})", text)
        if match:
            return f"After the discount: {say(number(match[2]) * (1 - number(match[1]) / 100))}."
        match = re.fullmatch(rf"(?:what is |how much is )?({token}) plus ({token}) percent tax", text)
        if match:
            return f"With tax: {say(number(match[1]) * (1 + number(match[2]) / 100))}."
        match = re.fullmatch(rf"(?:find the )?percentage increase from ({token}) to ({token})", text)
        if match:
            start = number(match[1])
            return "Percentage increase from zero is undefined." if start == 0 else f"The percentage change is {say((number(match[2]) - start) / abs(start) * 100)}%."
        match = re.fullmatch(rf"calculate a ({token}) percent tip(?: on ({token}))?", text)
        if match:
            return "Tell me the bill amount to calculate the tip." if not match[2] else f"The tip is {say(number(match[1]) * number(match[2]) / 100)}."
        match = re.fullmatch(rf"split a bill of ({token}) (?:between |for )?({token}) ways", text)
        if match:
            people = number(match[2])
            return "The number of people must be positive." if people <= 0 else f"Each person pays {say(number(match[1]) / people)}."
        match = re.fullmatch(rf"convert ({token}) (kilometers|kilometres|miles|kilograms|pounds|liters|litres|inches|hours|minutes|months) to (miles|kilometers|kilograms|pounds|milliliters|centimeters|seconds|hours|years)", text)
        if match and UNITS.get(match[2], (None,))[0] == match[3]:
            return f"{say(number(match[1]) * UNITS[match[2]][1])} {match[3]}."
        match = re.fullmatch(rf"convert ({token}) (fahrenheit|celsius) to (fahrenheit|celsius)", text)
        if match:
            value = number(match[1])
            result = ((value - 32) * 5 / 9 if match[2] == "fahrenheit" and match[3] == "celsius"
                      else value * 9 / 5 + 32 if match[2] == "celsius" and match[3] == "fahrenheit" else value)
            return f"{say(result)} degrees {match[3].capitalize()}."
        if re.fullmatch(r"how many centimeters are in an inch", text):
            return f"{say(UNITS['inches'][1])} centimeters."
        return None

    def _currency(self, text):
        match = re.fullmatch(r"(?:convert|how much is) (\d+(?:\.\d+)?) (usd|eur|gbp|inr|cad|dollars?|euros?|pounds?|rupees?) (?:in|to) (usd|eur|gbp|inr|cad|dollars?|euros?|pounds?|rupees?)(?: today)?", text)
        rate_only = re.fullmatch(r"current exchange rate of (usd|eur|gbp|inr|cad|dollars?|euros?|pounds?|rupees?) to (usd|eur|gbp|inr|cad|dollars?|euros?|pounds?|rupees?)", text)
        if rate_only:
            amount, source_name, target_name = Decimal(1), rate_only[1], rate_only[2]
        elif match:
            amount, source_name, target_name = Decimal(match[1]), match[2], match[3]
        else:
            return None
        source = CURRENCY.get(source_name, source_name.upper())
        target = CURRENCY.get(target_name, target_name.upper())
        if source == target:
            return f"{say(amount)} {source}."
        key = (source, target)
        with self.lock:
            cached = self.rates.get(key)
            if cached and time.monotonic() - cached[0] < 3600:
                data = cached[1]
            else:
                try:
                    response = self.http_get(f"https://api.frankfurter.dev/v2/rate/{source.lower()}/{target.lower()}", timeout=(.6, 1.2))
                    response.raise_for_status()
                    data = response.json()
                    if Decimal(str(data["rate"])) <= 0:
                        raise ValueError("Invalid exchange rate")
                    self.rates[key] = (time.monotonic(), data)
                except (requests.RequestException, OSError, ValueError, KeyError, TypeError, InvalidOperation):
                    return "I couldn't verify the current exchange rate."
        converted = say(amount * Decimal(str(data['rate'])))
        prefix = f"1 {source} equals" if rate_only else f"{say(amount)} {source} is"
        return f"{prefix} {converted} {target}, using the {data.get('date', 'latest available')} reference rate."

    def _system(self, text):
        if text in {"how hot is my gpu", "what is my gpu temperature"}:
            try:
                result = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu",
                    "--format=csv,noheader,nounits"], capture_output=True, text=True,
                    timeout=1.5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                temperature = int(result.stdout.strip().splitlines()[0])
                return f"Current GPU temperature is {temperature}°C."
            except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
                return "I couldn't read the current GPU temperature."
        if text in {"is my internet connected", "are you online"}:
            try:
                with socket.create_connection(("1.1.1.1", 443), timeout=1.0):
                    return "I can reach the internet right now."
            except OSError:
                return "I couldn't verify internet connectivity from this PC right now."
        if text in {"which model are you using", "what model are you using"}:
            model = (self.settings.get("knowledge") or {}).get("model")
            return f"My configured question model is {model}." if model else "I couldn't read my configured question model."
        if not (re.fullmatch(r"(?:what is |how much is )?(?:my )?(?:cpu usage|battery percentage|ram (?:free|available)|disk space (?:remaining|free))", text)
                or re.fullmatch(r"how much (?:ram|disk space) is (?:free|available)", text)):
            return None
        try:
            import psutil
            if "cpu" in text:
                return f"Current CPU usage is about {psutil.cpu_percent(interval=.1):.0f}%."
            if "battery" in text:
                battery = psutil.sensors_battery()
                return f"Battery is at {battery.percent:.0f}%." if battery else "Battery data is unavailable on this PC."
            if "ram" in text:
                return f"Available RAM is {psutil.virtual_memory().available / 2**30:.1f} GB."
            drive = Path.home().anchor or "C:\\"
            return f"Free space on {drive} is {shutil.disk_usage(drive).free / 2**30:.1f} GB."
        except (ImportError, OSError):
            return "I couldn't read current PC telemetry."

    def _random(self, text):
        if text == "flip a coin":
            return random.choice(("Heads.", "Tails."))
        if text in {"roll a dice", "roll a die"}:
            return f"I rolled {random.randint(1, 6)}."
        match = re.fullmatch(r"pick a random number from (-?\d+) to (-?\d+)", text)
        if match:
            a, b = map(int, match.groups())
            if a > b or b - a > 1_000_000_000:
                return "Give me a valid number range."
            return f"I picked {random.randint(a, b)}."
        return None

    def answer(self, question):
        text = re.sub(r"[?.!]+$", "", question.strip().casefold().replace("’", "'")).strip()
        for handler in (self._profile, self._dates, self._remote_time, self._math,
                        self._currency, self._system, self._random):
            result = handler(text)
            if result is not None:
                return result
        return None
