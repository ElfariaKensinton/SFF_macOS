SteaMidra v6.6.0

What's new:

### New features

* Added a **Reset Submitted Keys** button to the Provider page, allowing you to clear the submitted-key history and resubmit all provider keys without manually editing configuration files.
* Added a **DepotBox plan selector** to Settings. You can now switch between **Starter** and **Pro** rate limit plans directly from the application.
* DDMod terminal output is now captured directly into SteaMidra's logging system, keeping download diagnostics available without cluttering the terminal.

### Improvements

* Downloads are now fully integrated with the **Download Manager**. Both **Download through Steam (Fastest)** and **DepotDownloaderMod** downloads now appear in the Downloads tab with proper progress tracking.
* On Windows, SteaMidra now automatically removes the **read-only** attribute from Steam library root folders before downloading, helping prevent **Disk Write Error** issues while avoiding unnecessary recursive scanning.
* Greatly improved download responsiveness by removing the old stdout/stderr signal forwarding mechanism that could overwhelm the UI with thousands of progress updates per second.
* Improved the Store experience when disconnecting and reconnecting Hubcap. Saved API keys are now reused automatically, reconnects happen without unnecessary prompts, and search reliability has been improved.
* Settings now clearly indicate when encrypted API keys have been saved by displaying a green **✓ Saved** badge next to protected fields.

### Fixes

* Fixed an issue where the Store tab could become stuck loading forever after disconnecting and reconnecting a provider. All searches now consistently follow the same asynchronous update path.
* Fixed Hubcap API keys being deleted when disconnecting. Disconnecting now only ends the active session while keeping your saved credentials intact.
* Fixed Hubcap reconnects unnecessarily prompting for an API key even when one was already saved.
* Fixed Store pagination so pages beyond the first now correctly display their own results instead of repeating page one.
* Fixed the automatic **Enable Steam Updates** prompt appearing even when automatic updates for newly downloaded games were already enabled.
* Fixed Linux installations sometimes showing **Purchase** instead of **Play** by ensuring SLSsteam ownership settings are always applied and preserved.
* Fixed a critical Linux DepotDownloaderMod crash that prevented downloads from completing, ACF files from being written, SLSsteam configuration from updating, and downloaded games from being registered in the library.
* Fixed CreamAPI configuration generation writing an incorrect backup DLL path.
* Fixed a Linux ACF writer crash caused by a missing `sys` import.
* Fixed generated Linux `run.sh` launchers pointing to the wrong application entry point.

Full detailed changelog is in CHANGELOG.md
