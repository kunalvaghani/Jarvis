"""Readiness and golden diagnostics. User requests execute through the existing brain."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--golden', choices=('foundation_status', 'pint_si_and_temperature'))
    args = parser.parse_args()
    if args.golden:
        from .golden import run
        receipt, _ = run(args.golden)
        print(receipt.model_dump_json())
        return 0 if receipt.passed else 1
    from .catalog import enabled, manifests
    from .sandbox.env_manager import units_environment
    config = json.loads((Path(__file__).resolve().parents[2] / 'config/config.json').read_text(encoding='utf-8'))
    print(json.dumps({'lab_enabled': enabled(config), 'owned_manifests': len(manifests()),
                      'units_environment': units_environment(), 'always_on_lab_services': 0,
                      'scientific_acceptance': 'NOT_RUN'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
