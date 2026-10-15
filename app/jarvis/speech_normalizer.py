"""Bounded English speech rendering; never alters the visible/stored answer."""
import re
from .natural_voice import speech_unicode

SMALL = ('zero one two three four five six seven eight nine ten eleven twelve thirteen '
         'fourteen fifteen sixteen seventeen eighteen nineteen').split()
TENS = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()


def integer(value):
    number = int(value)
    if number < 0:return 'minus ' + integer(-number)
    if number < 20:return SMALL[number]
    if number < 100:return TENS[number//10] + (' ' + SMALL[number%10] if number%10 else '')
    if number < 1000:return SMALL[number//100] + ' hundred' + (' ' + integer(number%100) if number%100 else '')
    for scale, name in ((10**9,'billion'),(10**6,'million'),(1000,'thousand')):
        if scale <= number < scale*1000:
            return integer(number//scale)+' '+name+(' '+integer(number%scale) if number%scale else '')
    return ' '.join(SMALL[int(d)] for d in str(number))


def decimal(value):
    whole, dot, fraction = value.replace(',','').partition('.')
    return integer(whole) + (' point ' + ' '.join(SMALL[int(d)] for d in fraction) if dot else '')


def normalize(text):
    text = speech_unicode(text[:20000])
    def money(match):
        symbol, amount = match.groups()
        whole, _, fraction = amount.replace(',','').partition('.')
        unit = {'$':'dollar','£':'pound','€':'euro','₹':'rupee'}[symbol]
        spoken = integer(whole)+' '+unit+('s' if int(whole)!=1 else '')
        if fraction:
            cents = int(fraction.ljust(2,'0'))
            minor = 'paisa' if symbol == '₹' else 'penny' if symbol == '£' and cents == 1 else 'pence' if symbol == '£' else 'cent'
            spoken += ' and '+integer(cents)+' '+minor+('s' if symbol not in {'₹','£'} and cents!=1 else '')
        return spoken
    text = re.sub(r'([$£€₹])(\d[\d,]*(?:\.\d{1,2})?)(?!\d)', money, text)
    text = re.sub(r'https?://([^\s]+)', lambda m: m[1].replace('/', ' slash ').replace('.', ' dot ').replace('_',' underscore '), text)
    text = re.sub(r'\b[A-Za-z]:[\\/][^\s<>|]+', lambda m: m[0].replace(':',' drive').replace('\\',' slash ').replace('/',' slash ').replace('.',' dot '), text)
    text = re.sub(r'\b[a-zA-Z][a-zA-Z0-9]*(?:_[a-zA-Z0-9]+)+\b', lambda m:m[0].replace('_',' '), text)
    text = re.sub(r'([a-z])([A-Z])',r'\1 \2',text)
    for symbol, words in (('≤','less than or equal to'),('≥','greater than or equal to'),('≠','not equal to'),('∑','sum'),('√','square root'),('×','times'),('÷','divided by')):
        text = text.replace(symbol,' '+words+' ')
    text = re.sub(r'(?<![\w])\d[\d,]*(?:\.\d+)?(?![\w])',lambda m:decimal(m[0]),text)
    return text


def opening_clause(text):
    """Head with 6–8 words at punctuation, or eight with two words of lookahead."""
    words = list(re.finditer(r'\S+', text))
    for index in range(5,min(8,len(words))):
        if words[index][0].endswith((',', ';', ':', '.', '!', '?')):
            return words[index].end()
    return words[7].end() if len(words)>=10 else None
