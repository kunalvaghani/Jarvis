"""Supplementary catalog qualification, separate from the full tests-directory run."""
import pytest


def test_JRV_26_005_all_provider_observation_age_contract_incomplete():
    pytest.skip('BLOCKED: weather/air observation-age and clock-rollback fixtures passed; remaining provider source-time formats lack a complete freshness policy, so no all-adapter stale-as-live guarantee')
