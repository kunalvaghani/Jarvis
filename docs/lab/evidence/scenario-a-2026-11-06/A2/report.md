# 2026 F1-class conditional surrogate

Not exact F1 class engineering CAD. Not physically validated.

Source: https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_21_-_2026-10-19.pdf (issue 21, published 2026-10-19).

Geometry: independently checked procedural GLB and native Chrono JSON. No downloaded third-party model is claimed.

Experiment: identical prescribed controls, flat road, gravity, air and power unit across baseline/candidate. 2026 uses spatial front/rear coefficient modes; coefficients remain unmeasured assumptions.

Metrics are maximum observed speed, lateral acceleration and mechanical engine shaft energy in a 13-second road test; they are not terminal speed, race-lap performance or fuel/hybrid energy.

Half-timestep and +/-10% joint aero-envelope trials are retained. Other input intervals are declared but not exhaustively propagated.

```json
{
  "assumed_aero_envelope_candidate_ranges": {
    "maximum_observed_lateral_acceleration_m_s2": [
      6.801491714826554,
      6.8392253258365905
    ],
    "maximum_observed_speed_m_s": [
      10.934516021955433,
      10.939691646791863
    ],
    "mechanical_engine_energy_j": [
      2002027.144042558,
      2002461.8474435494
    ]
  },
  "baseline": {
    "maximum_observed_lateral_acceleration_m_s2": 6.804384657889096,
    "maximum_observed_speed_m_s": 10.937531963643067,
    "mechanical_engine_energy_j": 2002306.534108539
  },
  "candidate": {
    "maximum_observed_lateral_acceleration_m_s2": 6.801491714826554,
    "maximum_observed_speed_m_s": 10.937785323322391,
    "mechanical_engine_energy_j": 2002174.490051253
  },
  "candidate_minus_baseline": {
    "maximum_observed_lateral_acceleration_m_s2": -0.0028929430625419528,
    "maximum_observed_speed_m_s": 0.0002533596793234949,
    "mechanical_engine_energy_j": -132.04405728611164
  },
  "energy_scope": "mechanical engine shaft energy only; fuel/hybrid losses unsupported",
  "physical_validation": false,
  "scenario_sha256": "06dbb5437df3b30d61481c9172d7a178b0af171ff8a2e1fed9c67ba351dbb5a3",
  "speed_scope": "maximum observed in the fixed 13-second road test, not terminal or lap speed"
}
```

Replay numerical inputs with the approved fixed Chrono worker through Jarvis; each new execution requires an available invocation/budget slot. Read-only audit: `python -m jarvis.discovery.scenario_verify --manifest ".jarvis-runtime/discovery/scenario-projects/scenario-39a9ad2fff3a403ba945a01cd4f5e67b/run_manifest.json"`.
