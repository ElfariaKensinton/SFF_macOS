## 6.6.6

### New

* **Download Queue** — Queue multiple games from the Store with up to 3 parallel downloads, configurable in Settings. The Downloads tab now shows queued, active, completed, and failed downloads with live progress, Pause/Resume, Retry, Remove, and persistent auto-resume after restart.
* **Offline Store catalog** — A full store catalog now ships with SteaMidra, so the Store and search work instantly even without an internet connection.
* **Faster app-info lookups** — SteamCMD's JSON mirror is now the primary source, with Steam CM as a fallback. Download modals no longer block on Steam login.
* **Better older-version support** — Downgraded Build IDs and manifest IDs are now written into Steam's ACF and persistently retried if Steam is still using the file.

### Fixed

* Fixed game list updates failing when Valve rejects the bundled Steam Web API key by falling back to GitHub mirrors.
* Fixed Goldberg fixes failing when game files are locked or the game is still running.
* Fixed Linux archive extraction creating flat files with Windows-style backslashes instead of proper folders.
* Fixed DDMod downloads failing when the selected folder name contains colons.
* Fixed Windows Steam **"Disk write error"** and some invalid-content errors caused by SteaMidra making ACF files read-only.
* Fixed the Linux native downloader writing game files as flat filenames instead of their correct subfolders. A background repair also fixes previously affected installs.
* Fixed downloaded manifests not being moved into Steam's depotcache.
* Fixed several Steam CM freezes, cross-thread `gevent LoopExit` errors, DLC stalls, and MidraEveryDay downloads taking minutes.
* Fixed crack matching false positives between similarly named games.
* Fixed the DepotBox rate-limit dropdown rendering as a white native popup on Windows 11.
* Removed unused `MountedDepots` blocks from ACF patching.

### Improved

* **Memory management** — Added hourly cleanup for browser cache and Python memory to reduce memory growth during long sessions.
* **SteamTools/OST Lua support** — SteaMidra can detect depot-key Lua files in `config/lua` and offer to migrate new files into LumaCore's `stplug-in` folder.
* **Faster background branch lookups** — Background requests now use bounded fetches and can no longer hold the Steam connection for minutes.
* **Discord links updated** — The new community invite is now available throughout the README, documentation, Home, and Settings pages.
* **UI polish** — Improved custom dropdowns, modal scrollbars, and removed the misleading achievement-setup step from download progress.
