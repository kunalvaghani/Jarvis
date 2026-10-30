"""Requests Jarvis refuses before doing anything: system security and core system state stay with the user.

Checked on the whole request (a task or a compound "open X and ..."), before planning, so no app is
opened and no step is tried. Viewing is fine ("open registry editor"); changing is refused.
"""
import re

CHANGE = r'(?:delete|remove|erase|wipe|clear|edit|change|modify|add|create|rename|set|overwrite|tamper|reset)'
RULES = (
    (re.compile(rf'\b{CHANGE}\b.*\b(?:registry|regedit|reg key|run key|hk(?:lm|cu|ey_[a-z_]+))\b|'
                rf'\b(?:registry|regedit|reg key|run key|hk(?:lm|cu|ey_[a-z_]+))\b.*\b{CHANGE}\b', re.I),
     'changing the Windows registry can break Windows or let malware start, so I leave it to you.'),
    (re.compile(r'\b(?:disable|turn off|switch off|stop|uninstall|bypass|kill)\b.*\b(?:windows defender|defender|antivirus|'
                r'firewall|uac|user account control|smartscreen|bitlocker|secure boot|windows update|tamper protection)\b', re.I),
     'turning off Windows security protections is something only you should do.'),
    (re.compile(r'\b(?:click|press|accept|approve|answer)\b.*\b(?:uac|user account control|admin(?:istrator)? prompt|'
                r'elevation prompt|secure desktop)\b', re.I),
     'Windows security prompts are for you to answer; I never click them.'),
    (re.compile(r'\b(?:format|wipe|erase)\b.*\b(?:[a-z] ?drive|[a-z]:\\?|disk|partition|hard drive|ssd)\b|'
                r'\b(?:delete|remove|erase)\b.*\b(?:system32|windows folder|program files|boot ?loader|bcd)\b|\bdiskpart\b|\bbcdedit\b', re.I),
     'that could destroy Windows or your data.'),
    (re.compile(r'\b(?:show|reveal|export|copy|send|list|dump|extract)\b.*\b(?:saved|stored|browser|chrome|windows)\b.*\bpasswords?\b', re.I),
     'saved passwords stay private; I never read or move them.'),
)


def refusal(text):
    """A plain-language refusal when the request is off limits, else None."""
    value = ' '.join(str(text or '').split())
    for pattern, reason in RULES:
        if pattern.search(value):
            return "I can't do that, even with your approval: " + reason
    return None
