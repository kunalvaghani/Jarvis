# Upstream and compatibility — checked2026-10-16 IST

Firecrawl primary-source review: [exact URLs/dates](upstream-checks.json). [Playwright network documentation](https://playwright.dev/python/docs/network) recommends blocking service workers for reliable request interception. [BrowserContext WebSocket route API](https://playwright.dev/python/docs/api/class-browsercontext#browser-context-route-web-socket) is available in installed1.63.0. Real Chrome execution verified these APIs. Fresh contexts do not borrow user authentication/storage.

[PyPI Playwright](https://pypi.org/project/playwright/) reports1.64.0, released2026-10-13; installed1.63.0 retained. [Python release notes](https://playwright.dev/python/docs/release-notes) currently lead with1.63; registry release and documentation coverage are recorded separately. No new browser/package downloaded or1.64 acceptance claimed.

[Vite preview options](https://vite.dev/config/preview-options) documents strictPort failure instead of port hopping. [Vite8.3.4 release notes](https://github.com/vitejs/vite/releases/tag/v8.3.4), displayed2026-10-08, describe HMR-default, preload and style fixes; installed fixture8.3.2 was actually built. No new dependency installation or measured version-comparison claim. Production previews remain distinct from HMR.

Node24.14.0/npm11.11.1, TypeScript7.0.2, axe-core4.13.0, Python3.10.6, Playwright1.63.0. Package pins retained; this is not a full npm/transitive advisory census. Prior [module21 compatibility](../21-native-coding/compatibility.md) records older Git/Python lifecycle risks. Chrome channel is the installed browser, not a reproducible bundled revision. GPU inference not used. ready launcher snapshot; no native Electron/Expo device or autonomous model-generated website acceptance.
