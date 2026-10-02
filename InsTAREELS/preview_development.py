"""Time-bounded owned preview of the already verified acceptance dashboard."""
import argparse
from pathlib import Path
import time
from jarvis.development_tools import DevelopmentTools

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minutes',type=int,default=30)
    args=parser.parse_args()
    if not 1<=args.minutes<=60:parser.error('Choose 1–60 minutes.')
    base=Path(__file__).resolve().parent
    stop=base/'.jarvis-runtime/stop'
    marker=stop.stat().st_mtime_ns if stop.exists() else 0
    tools=DevelopmentTools(base)
    try:
        url=tools.start_preview(base/'artifacts/development-dashboard','vite',lambda:False)
        print(url,flush=True)
        until=time.monotonic()+args.minutes*60
        while time.monotonic()<until:
            if stop.exists() and stop.stat().st_mtime_ns>marker:break
            if not tools.healthy():
                tools.repair()
                break
            time.sleep(.5)
    finally:tools.close()

if __name__=='__main__':main()
