# Remaining failure: P33-004 — P1 / PARTIAL

The old unlabelled credential-switch repro now passes, as do changed-label, stable-context and token-on-card controls. However ProviderContext.verified means only that non-secret identity keys are nonempty. recheck treats any replacement credential with unchanged identity text as verified same-account rotation. It does not establish which principal owns that credential.

Independent JRV-33-022 fixture starts label account-a@example.test and token A. While approval is pending it replaces only the token with one assigned to mock account B. The approval still displays account A and identity_verified:true. The adapter dispatches POST with B's credential and A's event body. The stable-token control writes only to mock A. All provider HTTP is intercepted, so no real event/network request occurred. See configured-switch.json, configured-stable.json and configured-identity.xml.

Exact failing test: test_JRV_33_022_configured_label_does_not_verify_a_replacement_token[other-account-token]. Source: jarvis/provider_identity.py ProviderContext.__init__ verified assignment and recheck current.rotated branch; jarvis/toolkits.py passes the rechecked context to dispatch. This is the acknowledged unverified-rotation limit in Claude's repair notes, independently reproduced, not a newly claimed real provider exploit or external process environment mutation. Same underlying P33-004 remains OPEN/PARTIAL; no replacement finding ID or downgrade.

P33-001/002/003 and original P32-001/002 reproductions PASS at the new SHA. Schema array/enum/result fixes are verified within the tested supported subset. These passes do not establish full account, concurrency, memory/schema migration or live module acceptance.
