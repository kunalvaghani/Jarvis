"""Two bounded parser goldens; no research assets or Scenario A answers.

Uses the existing approved mechanics environment and shared 50-call ledger.
Original test geometry is constructed analytically with standard-library code.
"""
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys

APP=Path(__file__).resolve().parents[2]/'app'
sys.path.insert(0,str(APP))


from jarvis.discovery.adapters.asset_inspection_goldens import cases


def main():
    from jarvis.discovery.adapters import asset_inspection as adapter
    from jarvis.neural.journal import Journal
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-full-a',action='store_true')
    args=parser.parse_args()
    from jarvis.discovery.adapters.asset_resources import grant
    permission_sha=grant()['sha256'] if args.approved_full_a else None
    journal=Journal(APP/'.jarvis-runtime/lab-validation/asset-inspector-golden.sqlite3')
    try:print(json.dumps(adapter.ensure_qualified(journal,resource_grant_sha256=permission_sha)))
    finally:journal.close()



if __name__=='__main__':main()
