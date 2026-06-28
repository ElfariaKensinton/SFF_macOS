SteaMidra v6.3.2
What's new:
- LumaCore Denuvo DRM support (auto-detect, auth window, eticket safety net, new Lua bindings)
- LumaCore EOS multiplayer bridge (LumaCorePayload.dll, auto-create device IDs, auto-propagate to child processes)
- LumaCore IPC dispatch survives Steam updates (TOML-based method specs, network mirror cache, no rebuild needed)
- LumaCore config hot-reload (lumacore.toml watches for disk changes, no Steam restart)
- LumaCore on-demand e-ticket minting + new Lua bindings (lcHttpPost, fetchManifestCode, getCachedAppTicket, addtoken, setAppticket, setEticket)
- LumaCore achievement fixes for online-fix (m_nGameID rewriting, achievements unlock on the right game)
- LumaCore pipe identity tracking, ownership marking, and expanded diagnostics (20 per-module logs, boot diagnostic popup)
- Keyring crash fix on Linux (secret store falls back to local file encryption when kwallet/gnome-keyring is missing)
- Chrome for Testing download works on Bazzite and Fedora Atomic (retries without SSL verification)
- Wrong SSD download fixed (checks every Steam library for the game's ACF before picking a destination)
- Game search survives Steam API outages (falls back to GitHub mirrors when the API is down)
- Multiplayer Fix overhauled (opens online-fix.me in browser instead of auto-downloading, search engine fallback, one-time popup)
- oureveryday downloads reuse cached .lua files instead of re-fetching every time
- SteamAutoCrack NO LICENSE error fixed (API key written even when config.json is missing)
- SteamAutoCrack STEAMLESS-ONLY crash fixed (bad config key with space in alias stripped before CLI sees it)
- Workshop browser renders properly now (waits for page load before showing, no more half-gray flash)
- Performance fix (settings file cached in memory instead of hitting disk on every UI tick)
- LumaCorePayload.dll tracked during install, uninstall, and cleanup
- Installer improvements (Defender exclusion prompt removed, runs at user level by default, installs to AppData without admin)
- Windows floppy drive stall fixed, Chrome platform detection works on Linux/macOS, various other crash fixes

Full detailed changelog is in CHANGELOG.md
