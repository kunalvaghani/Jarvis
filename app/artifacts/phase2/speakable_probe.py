"""Print what the voice engines receive for adversarial reply text (spoken_text -> tts_text)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis.speech import spoken_text
from jarvis.natural_voice import tts_text
CASES = [
    r'Saved to C:\Users\kunal\Documents\report_v2.docx today.',
    'It costs $5.99 or ₹450, about 12.5% more.',
    'x³/3 + C, √2 ≈ 1.414, n(n+1)/2',
    'Email kunal@example.com or visit www.example.com/docs.',
    '| Name | Value |\n| --- | --- |\n| cpu_threads | 12 |',
    'Traceback (most recent call last):\n  File "main.py", line 42, in <module>\n    raise ValueError("bad")\nValueError: bad',
    'Set gpu_layers to 9 in getUserName at 5:30 PM on 2026-10-15.',
    '日本語のテキスト mixed',
]
for case in CASES:
    print(json.dumps(tts_text(spoken_text(case)), ensure_ascii=False))
