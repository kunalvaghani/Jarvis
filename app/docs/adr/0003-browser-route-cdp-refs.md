# ADR 0003: Browser route refs come from Chrome's accessibility tree over CDP

Date: 2026-10-30 · Status: accepted

## Context

Doc section 12.2 sketches refs by injecting JavaScript that writes `data-jarvis-ref` attributes into the page. That mutates the DOM. It also lets page scripts read, move or forge refs: a page could copy `data-jarvis-ref="ref_3"` onto a different button, which is exactly the "button relabelled mid-action" attack in doc section 13. The reverse-engineered Claude in Chrome design keeps its refs in a page-world map (doc 6.2, `[RE]`), which page scripts can reach too.

## Decision

Route 2 reads the tree with CDP `Accessibility.getFullAXTree` (per frame; out-of-process iframes get their own CDP session) and keys refs by `(frame id, backendDOMNodeId)` in `RefRegistry`. Nothing is written into the page.

- **Visibility** comes from one `DOMSnapshot.captureSnapshot` per read: nodes without layout are not rendered, and "visible" means the layout box intersects the viewport. Page reads are built from rendered content only (doc 2.3 item 9).
- **Pointer actions on a ref:** scroll into view, wait for the box to stay put across two reads, refuse disabled targets, hit-test the centre with `DOM.getNodeForLocation` (the node or one of its descendants must receive the click), then dispatch through Playwright's mouse (CDP `Input`). This mirrors Playwright's actionability checks without DOM injection.
- **Form input:** `DOM.focus` plus native value setting through `Runtime.callFunctionOn` on the resolved node, firing `input`/`change` (doc 6.2), then reading the value back.
- **Refs are invalidated** for a tab on main-frame navigation. Nodes that vanish are dropped individually on the next read (`RefRegistry.retain`).
- **Every request**, including subresources, redirects and iframe loads, passes `Policy.check_url` through `context.route("**/*")` (doc 4).
- **Browser binary:** installed Chrome via `channel="chrome"`, matching the existing worker. Playwright 1.63's bundled Chromium build 1243 is not downloaded and is not needed.

Verified by a 2026-10-30 prototype against installed Chrome 155: the full tree read took 5.1 ms on a small page, `display:none` content was excluded, label association was correct, and box models resolved by backend node id.

## Consequences

Refs survive DOM changes that keep the node and cannot be forged by page script. Rendered-but-deceptive text (white-on-white) is still read, so the planner boundary must keep treating page text as data (Phase 6 tests this).
