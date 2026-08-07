## 6.6.2

### Fixed

- **Library tab "No games found" crash** — `_bridge_load_library`, `_bridge_fetch_library_images`, and `_bridge_cancel_bulk_import` had stale `self.` references that were not converted to `bridge.` during the web_bridge.py refactoring, causing `NameError: name 'self' is not defined`. Library tab, cloud saves, and bulk import now work correctly.
- **Cloud saves `WebBridge` reference crash** — `cloudsaves_bridge.py` had 5 stale `WebBridge._get_bundled_tool_path()` references (lines 151, 207, 249, 484, 644) left over from the bridge extraction. Changed to `bridge._get_bundled_tool_path()`.