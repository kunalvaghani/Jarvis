"""Normalize only a fully recognized bounded divider utterance, never arbitrary text."""
import re
import unicodedata

NUMBER=r'([+-]?(?:\d{1,12}(?:\.\d{0,12})?|\.\d{1,12}))'
DIVIDER=re.compile(r'^\s*(?:jarvis[, ]+)?lab\s+simulate\s+divider\s+'+NUMBER+r'\s*(?:V|volts?)\s*[,;]?\s+'
                   +NUMBER+r'\s*(?:Ω|ohms?)\s*[,;]?\s+(?:and\s+)?'+NUMBER+r'\s*(?:Ω|ohms?)[.!?\s]*$',re.I)
PREFIX=re.compile(r'^\s*(?:jarvis[, ]+)?lab\s+simulate\s+divider\b',re.I)


def normalize_command(command):
    if command.kind not in ('task','ask') or command.extra not in ('','unparsed'):return command
    value=unicodedata.normalize('NFKC',command.value)
    match=DIVIDER.fullmatch(value)
    if not match:
        if PREFIX.match(value):
            raise ValueError('Use lab simulate divider with three numeric values in V, ohm, ohm; unsupported scientific syntax is not sent to the general planner.')
        return command
    from jarvis.commands import Command
    return Command(command.kind,f'lab simulate divider {match[1]} V {match[2]} ohm {match[3]} ohm',command.extra)
