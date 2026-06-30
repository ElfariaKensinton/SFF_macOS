SteaMidra v6.3.7

What's new:

* Remove DRM button in the web UI no longer crashes SteaMidra. The action is now routed through the main thread, fixing the Qt6 QThread crash.
* Auto Update checkboxes no longer affect other games by accident. Shared redist depots like DX, VC++, and .NET runtimes are now filtered out so unchecking one game does not silently uncheck others that share the same depot.
* Provider metadata enrichment now resolves parent app IDs for orphan depots using the bundled provider database. Depots from config.vdf and Lua files without a plain addappid line now get proper names, kinds, and parent info instead of staying as generic “Depot 12345” entries.
* Modern GUI blank/grey screen issue fixed on some NVIDIA/AMD setups. Removed problematic Chromium GPU flags, added one-time renderer crash recovery, and added a dark error page when the page fails to load fully.
* Oureveryday manifest downloads are more reliable. Added three GitHub manifest mirror repos to the cascade, so if one mirror is down, the next one can still catch it.
* Manifest download cascade reordered: GMRC mirrors → GitHub repos → ManifestHub → encrypted GMRC endpoint as last resort. ManifestHub outages no longer block GitHub fallback access.
* Cloud Saves now backs up custom save paths from the Ludusavi manifest database, covering 22k+ games.
* Games that save outside Steam userdata, such as Lies of P under `LiesofP/Saved/SaveGames/`, are now included alongside Steam remote data.
* Removed online-fix.me username and password fields from Settings, since the feature no longer auto-downloads and those credentials are no longer needed.

Full detailed changelog is in CHANGELOG.md
