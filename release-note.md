SteaMidra v6.3.6

What's new:

* Remove DRM button in the web UI no longer crashes SteaMidra. The action is now routed through the main thread like SteamAutoCrack, fixing the Qt6 QThread crash.
* LumaCore `add_ids` warning is gone. LumaCoreManager now writes minimal Lua stubs for each app ID instead of throwing NotImplementedError during downloads or local imports.
* Home tab game dropdown now refreshes when you return to the page. Newly installed games should appear without waiting for the old 10-minute refresh timer or restarting the app.
* Hubcap key decryption failures are now logged at startup, making it clear when the encryption key changed and the saved API key can no longer be read.
* Cloud Saves now backs up custom save paths for games that store saves outside Steam userdata.
* Ludusavi manifest support added for Cloud Saves, covering 22k+ games. Games like Lies of P, which save under `LiesofP/Saved/SaveGames/`, are now backed up together with Steam remote data.
* Removed online-fix.me username and password fields from Settings, since the feature no longer auto-downloads and those credentials are no longer needed.

Full detailed changelog is in CHANGELOG.md
