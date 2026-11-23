"""Offline, read-only replay of exported Scenario A numerical/file evidence."""
import argparse,csv,hashlib,json
from pathlib import Path
from .scenario_checks import files,compare
from .vehicle_checks import study
from .model.vehicle import VehicleCase


def verify(base,relative):
    from .adapters.assets import local_bytes
    if not relative.startswith('.jarvis-runtime/discovery/scenario-projects/') or not relative.endswith('/run_manifest.json'):
        raise ValueError('owned run manifest path required')
    manifest=json.loads(local_bytes(Path(base),relative,500_000));files(base,manifest['files'])
    root=Path(base)/Path(relative).parent
    case=VehicleCase.model_validate_json((root/'solver_configuration.json').read_text())
    report=json.loads((root/'raw_solver_output.json').read_text())
    checks=study(case,report)
    if manifest['comparison']!=compare(report):raise ValueError('exported metrics changed')
    with (root/'raw_output.csv').open(newline='') as stream:rows=list(csv.DictReader(stream))
    expected=[(run['variant'],row) for run in report['reports']['primary']['runs'] for row in run['samples']]
    if len(rows)!=len(expected):raise ValueError('CSV sample count differs')
    for row,(variant,raw) in zip(rows,expected):
        if row['variant']!=variant or row['mode']!=raw['mode']:raise ValueError('CSV scenario/variant differs')
        for key in ('time_s','speed_m_s','lateral_acceleration_m_s2','mechanical_engine_energy_j','front_flap_angle_deg','maximum_constraint_residual'):
            if float(row[key])!=raw[key]:raise ValueError('CSV numeric value differs from raw solver output')
        if [float(row[key]) for key in ('x_m','y_m','z_m')]!=raw['position_m']:raise ValueError('CSV trajectory differs')
    return {'passed':True,'scope':'offline exported numerical/file consistency, not fresh execution or physical validation',
        'run_id':manifest['run_id'],'verification':checks,'physical_validation':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',required=True);args=parser.parse_args()
    print(json.dumps(verify(Path(__file__).resolve().parents[2],args.manifest)))


if __name__=='__main__':main()
