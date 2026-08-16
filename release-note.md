## 6.6.5

### New

* **Automatic Build ID downloads** — Download Older Version can now select a Build ID from SteamDB and automatically retrieve the matching depot manifests through DepotBox. Manual manifest selection remains available.
* **Provider credits** — Ryuu, DepotBox, and Hubcap now have dedicated credits and community-server links in the download UI and Settings.
* **Crack notifications** — Download dialogs now show available crack information and can guide you to the required Build ID. Installed games can also detect mismatched crack builds and offer to apply the correct crack.
* **SteamCMD app-info fallback** — Added a reliable SteamCMD app-info mirror for faster and more reliable game metadata lookups.
* **Downgrade tracking** — Older-version installs now update Steam's ACF with the selected Build ID and manifests, with automatic retry if the ACF is unavailable or locked.
* **MidraEveryDay** — OurEveryday has been renamed to MidraEveryDay.

### Fixes

* Fixed Ryuu downloads crashing because of a missing import.
* Fixed DLC names being missing from generated MidraEveryDay Lua files.
* Fixed the Linux native downloader not starting because of multiple runtime errors.
* Fixed several Store freezes, including startup, landing-page loading, and rapid searches.
* Fixed download modals freezing for extended periods while fetching app and branch information.
* Fixed older-version downloads incorrectly prompting to enable auto-updates.
* Fixed malformed Build ID responses being accepted.
* Fixed DDMod partial-download failures and improved fallback handling.
* Fixed GUI freezes caused by blocking network and disk operations.
* Fixed LumaCore support data not being restored automatically after Steam updates.

### Improved

* **Store performance** — Offline-first browsing, search request coalescing, better worker handling, reduced memory usage, and various UI performance improvements.
* **Download performance** — App-info and branch lookups are now much faster and no longer block the UI.
* **Store errors** — Failed searches now display proper error messages instead of failing silently.
* **Linux documentation** — Updated `LINUX_SETUP.md` with the correct `LD_AUDIT` terminology.
