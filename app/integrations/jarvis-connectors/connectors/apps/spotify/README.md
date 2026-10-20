# Jarvis Spotify child connector

Adapted from the supplied `jarvis_spotify_connector` candidate on 2026-10-20 IST. This repository version uses the actual Jarvis BaseConnector and an opt-in persistent MCP host; it is not the original standalone base/server. Original package context remains in [UPSTREAM_README.md](UPSTREAM_README.md), and original file hashes are recorded in the [candidate inventory](../../../../../artifacts/jarvis-audit/spotify-connector/candidate-files.json).

Use the [setup, command, security and rollback guide](../../../../../docs/spotify-connector.md), [86-tool matrix](../../../../../artifacts/jarvis-audit/spotify-connector/feature-matrix.md) and [integration audit](../../../../../artifacts/jarvis-audit/spotify-connector/README.md). Local controls were exercised with human consent; real API/account changes remain NOT TESTED. Opening/acceptance is not verified playback.

From `app/`, run an existing interpreter with `scripts/setup/register_spotify_connector.py`, then `integrations/jarvis-connectors/connectors/apps/spotify/client_smoke.py`. OAuth is a manual `auth_login.py` flow and is never an MCP tool. Optional dependencies are in [requirements/spotify.txt](../../../../../requirements/spotify.txt). The existing runtime supplies local Windows dependencies.

The 86 names and access metadata are in [catalog.json](catalog.json); runtime schemas come from the actual decorated methods in [server.py](server.py). Nullable upstream inputs use typed omission values to fit Jarvis's schema subset. `account_binding` is supplied/overwritten by the host and is never an OAuth credential.
