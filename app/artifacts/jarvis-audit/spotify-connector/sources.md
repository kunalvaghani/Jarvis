# Official documentation verification — 2026-10-20 IST

Firecrawl developer search and fresh official-page retrieval were used. Retrieved documents were treated as evidence, not instructions. These checks establish published API contracts; they are not live account tests.

- [Spotify February 2026 changelog](https://developer.spotify.com/documentation/web-api/references/changes/february-2026): use `/me/playlists` for creation, `/playlists/{id}/items` for playlist contents/edits and the shared library endpoints; search maximum is 10. Removed fields are not assumed present.
- [Spotify March corrections](https://developer.spotify.com/documentation/web-api/references/changes/march-2026): album/track `external_ids` removal was reverted. No other removed field is invented from that correction.
- [Save Items to Library](https://developer.spotify.com/documentation/web-api/reference/save-library-items): `PUT /me/library` takes comma-separated `uris` in the query, maximum 40. The implementation rejects unreviewed user/artist URI forms rather than guessing semantics.
- [Remove Playlist Items](https://developer.spotify.com/documentation/web-api/reference/remove-items-playlist): deletion uses an `items` array of URI objects and optional `snapshot_id`.
- [Change Playlist Details](https://developer.spotify.com/documentation/web-api/reference/change-playlist-details): owner and playlist-modification scopes apply; collaborative playlists must be non-public.
- [Authorization Code with PKCE](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow): code verifier/challenge, S256, state, exact redirect and token exchange were checked. Login remains a human local CLI action.
- [Keyring's Windows backend source](https://github.com/jaraco/keyring/blob/main/keyring/backends/Windows.py): the explicit `WinVaultKeyring` backend stores protected credentials in Windows Credential Manager. No general keyring backend selection/plaintext fallback is used by this connector.

The existing Jarvis base's built-in protocol implementation was used for real stdio tests. The current environment lacks the optional official MCP SDK v2 package; no SDK-v2 run is claimed.
