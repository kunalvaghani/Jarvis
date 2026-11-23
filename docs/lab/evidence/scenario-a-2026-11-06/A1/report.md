# 2025 F1-class conditional surrogate

Not exact McLaren engineering CAD. Not physically validated.

Source: https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_15_-_2025-12-10_0.pdf (issue 15, published 2025-12-10).

Geometry: independently checked procedural GLB and native Chrono JSON. No downloaded third-party model is claimed.

Experiment: identical prescribed controls, flat road, gravity, air and power unit across baseline/candidate. 2026 uses spatial front/rear coefficient modes; coefficients remain unmeasured assumptions.

Metrics are maximum observed speed, lateral acceleration and mechanical engine shaft energy in a 13-second road test; they are not terminal speed, race-lap performance or fuel/hybrid energy.

Half-timestep and +/-10% joint aero-envelope trials are retained. Other input intervals are declared but not exhaustively propagated.

```json
{
  "assumed_aero_envelope_candidate_ranges": {
    "maximum_observed_lateral_acceleration_m_s2": [
      6.8384458473288,
      6.942996785525512
    ],
    "maximum_observed_speed_m_s": [
      10.970118706045929,
      10.972207592507155
    ],
    "mechanical_engine_energy_j": [
      1999341.5087514797,
      2000327.6246914386
    ]
  },
  "baseline": {
    "maximum_observed_lateral_acceleration_m_s2": 7.04864124179014,
    "maximum_observed_speed_m_s": 10.974696685343812,
    "mechanical_engine_energy_j": 2000078.5586698526
  },
  "candidate": {
    "maximum_observed_lateral_acceleration_m_s2": 6.942996785525512,
    "maximum_observed_speed_m_s": 10.971575126053525,
    "mechanical_engine_energy_j": 1999908.5676813503
  },
  "candidate_minus_baseline": {
    "maximum_observed_lateral_acceleration_m_s2": -0.1056444562646277,
    "maximum_observed_speed_m_s": -0.0031215592902871236,
    "mechanical_engine_energy_j": -169.99098850227892
  },
  "energy_scope": "mechanical engine shaft energy only; fuel/hybrid losses unsupported",
  "physical_validation": false,
  "scenario_sha256": "ed194d5639d0bac27c5eb307ebcc0a3c064a489ec5c71a3da46cce948792e010",
  "speed_scope": "maximum observed in the fixed 13-second road test, not terminal or lap speed"
}
```

Replay numerical inputs with the approved fixed Chrono worker through Jarvis; each new execution requires an available invocation/budget slot. Read-only audit: `python -m jarvis.discovery.scenario_verify --manifest ".jarvis-runtime/discovery/scenario-projects/scenario-313b2842d9de42e68e893db1e2e7b0c4/run_manifest.json"`.
