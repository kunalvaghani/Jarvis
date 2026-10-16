# Reproduction and repair evidence

Baseline: 41 passed. Eight initial assertions failed: same-second concurrent session collision; four malformed configurations; invalid analysis output accepted; uncertain analysis replayed; oversized checkpoint accepted. [Reproduction](reproduction.xml), [log](reproduction.txt). First repairs: 17 passed. Expanded matrix first had 73 passed / 13 skips / 2 fixture setup errors: pytest used a 200 KB parameter value as an environment-variable test ID, exceeding Windows 32,767 characters. Short explicit parameter IDs repair this test-harness issue without weakening assertions. Next targeted run: 104 passed / 13 blocked skips. Expanded neighboring TaskState/recovery run: 127 passed / 13 blocked skips. Additional direct wrong-kind-list input reproduced an unhandled TypeError; kind validators now reject list/object/bool/number with ValueError. Four new regression variants pass. Final focused result: 131 passed / 13 blocked skips. The superseded full run was stopped at roughly 66 percent before this fix; its log/hash snapshot are preserved and do not count as completed validation. A fresh frozen full run validates final source.

Full-test skips are recorded separately; a full-regression pass does not waive any catalog blocker.

- **JRV-29-001 BLOCKED:** Owned Node bridge fixture verifies transport/readback, but no current REA analyzer accuracy oracle for an interactive demo app is implemented.
- **JRV-29-004 BLOCKED:** No remote-page content fingerprint or stale-observation classifier; URL registration does not fetch pages.
- **JRV-29-005 BLOCKED:** Evidence is explicitly untrusted and behavior unverified; screenshot-to-clone fidelity and inference labeling need a coding acceptance adapter.
- **JRV-29-006 BLOCKED:** REA bridge does not run generated-clone button interactions or require their E2E receipts.
- **JRV-29-007 BLOCKED:** No semantic secret-extraction request classifier or complete target-content secret filter; approved REA is not a security sandbox.
- **JRV-29-009 BLOCKED:** No screenshot/layout comparison adapter or visual tolerance oracle in the REA bridge.
- **JRV-29-010 BLOCKED:** Credentialed/private URLs reject, but account-protected analysis has no dedicated authorization capability or isolated browser-profile proof.
- **JRV-29-015 BLOCKED:** Invalid/nonobject/deep/oversized JSON rejects; command-specific required-field and type schemas remain incomplete.
- **JRV-29-021 BLOCKED:** NODE_PATH and API-key environment injection are absent in fixtures, but HOME/USERPROFILE/appdata and host network remain accessible to approved REA; no full cloud/cache/private-content oracle.
- **JRV-29-024 BLOCKED:** Programs and paths revalidate after approval, but recursive source changes and remote freshness/navigation races lack a content-bound receipt.
- **JRV-29-025 BLOCKED:** No host RAM/GPU pressure versus responsive core command experiment. No GPU inference is needed by this bridge fixture.
- **JRV-29-027 BLOCKED:** Ledger A/B has 20 warm and five initial samples; not five cold processes with complete REA/analyzer RSS/VRAM latency.
- **JRV-29-032 BLOCKED:** Session/attempt IDs and untrusted labeling exist; raw local evidence/ledger previews lack complete secret redaction and end-to-end trace correlation.
