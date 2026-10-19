"""Carry forward reviewed evidence-collection helpers, replace all verdict text for the new SHA."""
from pathlib import Path

out=Path(__file__).resolve().parent
prior=out.parent/'2026-10-19-independent-cd8861c/collect.py'
prefix=prior.read_text(encoding='utf-8').split('oldcases=')[0]
replacements={
 'Collect the cd8861c independent continuation':'Collect the 146ba83 independent confirmation',
 "OLD='2c4ea56eb7967929e49dad07b0612cb99caaf56e'":"OLD='cd8861ce720ade303485ee2023430dd8c6b4f0ba'",
 "SHA='cd8861ce720ade303485ee2023430dd8c6b4f0ba'":"SHA='146ba831e7ae5df1a953b0f910288c41c9ab4689'",
 "PRIOR=OUT.parent/'2026-10-19-independent-2c4ea56'":"PRIOR=OUT.parent/'2026-10-19-independent-cd8861c'",
 "'cross-pillar','configured-identity'":"'cross-pillar','optional-routes'",
 "packet_started_date='2026-10-19'":"packet_started_date='2026-10-20'",
 "date_note='Run crossed midnight IST; directory retains start date.'":"date_note='Fresh confirmation on 2026-10-20 IST.'",
 "'3469 passed/147 skips is author evidence, not independently added to totals'":"'3473 passed/147 skips is author evidence, not independently added to totals'",
 "'test_contract_edges.py','test_provider_context.py']":"'test_contract_edges.py','test_provider_context.py','test_configured_identity.py']",
 "'configured labels marked verified; changed credentials with same label accepted as rotation'":"'labels unverified; credential change rejected absent independent principal/workspace/scope confirmation; no production verifier registered'",
}
for before,after in replacements.items():
    assert before in prefix,before
    prefix=prefix.replace(before,after)
suffix=(out/'report_sections.py').read_text(encoding='utf-8')
(out/'collect.py').write_text(prefix+suffix,encoding='utf-8')
print('Collector built from preserved helper source with new SHA/data/reports.')
