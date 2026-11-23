# 2025 F1-class conditional surrogate

Not exact McLaren engineering CAD. Not physically validated.

Source: https://www.fia.com/sites/default/files/documents/fia_2025_formula_1_technical_regulations_-_issue_03_-_2025-04-07.pdf (issue 3, published 2025-04-07).

Geometry: independently checked procedural GLB and native Chrono JSON. No downloaded third-party model is claimed.

Experiment: identical prescribed controls, flat road, gravity, air and power unit across baseline/candidate. 2026 uses spatial front/rear coefficient modes; coefficients remain unmeasured assumptions.

Metrics are maximum observed speed, lateral acceleration and mechanical engine shaft energy in a 13-second road test; they are not terminal speed, race-lap performance or fuel/hybrid energy.

Half-timestep and +/-10% joint aero-envelope trials are retained. Other input intervals are declared but not exhaustively propagated.

```json
{
  "assumed_aero_envelope_candidate_ranges": {
    "maximum_observed_lateral_acceleration_m_s2": [
      6.905363327566213,
      6.957432224297405
    ],
    "maximum_observed_speed_m_s": [
      11.128570290984358,
      11.131841105356985
    ],
    "mechanical_engine_energy_j": [
      2000873.7992328894,
      2001916.1743459788
    ]
  },
  "baseline": {
    "maximum_observed_lateral_acceleration_m_s2": 6.8760716239675,
    "maximum_observed_speed_m_s": 11.133399505005473,
    "mechanical_engine_energy_j": 2001342.9052808278
  },
  "candidate": {
    "maximum_observed_lateral_acceleration_m_s2": 6.905363327566213,
    "maximum_observed_speed_m_s": 11.130075970577348,
    "mechanical_engine_energy_j": 2001428.8499868833
  },
  "candidate_minus_baseline": {
    "maximum_observed_lateral_acceleration_m_s2": 0.02929170359871236,
    "maximum_observed_speed_m_s": -0.0033235344281248302,
    "mechanical_engine_energy_j": 85.94470605556853
  },
  "energy_scope": "mechanical engine shaft energy only; fuel/hybrid losses unsupported",
  "physical_validation": false,
  "scenario_sha256": "07c97834a76fee660a3ea476b4efc41b05982f4a163662164ceb800553b4bf33",
  "speed_scope": "maximum observed in the fixed 13-second road test, not terminal or lap speed"
}
```

Replay numerical inputs with the approved fixed Chrono worker through Jarvis; each new execution requires an available invocation/budget slot. Read-only audit: `python -m jarvis.discovery.scenario_verify --manifest ".jarvis-runtime/discovery/scenario-projects/scenario-370d71d6335141d9ba268eb19893db4a/run_manifest.json"`.
