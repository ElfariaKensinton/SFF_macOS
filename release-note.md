SteaMidra v6.6.4

What's new:

### Linux fixes

* Fixed the Linux installer failing to install the required `steam` Python package. `steam==1.4.4` is now correctly installed into the SteaMidra virtual environment during setup, preventing `ModuleNotFoundError` crashes on startup.
* Fixed Linux game launching for **Proton/Wine games**. SteaMidra no longer searches only for native ELF executables and instead delegates launches through Steam, correctly supporting both native Linux games and Windows games running through Proton.
* Fixed downloads hanging on **Wayland** when modal dialogs were invisible. GUI-thread waits now have a 30-second timeout, while temporary download requests have a 120-second timeout instead of waiting indefinitely.
* Fixed existing ACF files that were read-only and could not be overwritten. SteaMidra now restores write permissions before updating them.

### Fixes

* Fixed **Crack Files** actions appearing to do nothing. Crack Fix, Multiplayer Fix, and Manage DLC operations now return proper success/error states and display feedback through UI notifications.
* Replaced the browser's native OK/Cancel dialog for the Auto Update prompt with SteaMidra's custom **Yes/No** confirmation dialog.
* Fixed the **Ryuu API key prompt loop**. SteaMidra now asks whether the key is for the Reseller or Premium endpoint before accepting it, ensuring the correct API is used. Failed authentication clears both stored keys.
* Fixed **DepotDownloaderMod progress** getting stuck at 95%. Progress can now correctly reach 100%.
* Fixed empty manifests being treated as successful downloads. The native downloader now rejects zero-byte manifest responses.
* Fixed `saved_lua/<appid>.lua` files remaining behind after removing a game. Game removal now cleans up the associated Lua file as well.
* Empty Hubcap API key input is now handled gracefully instead of causing unnecessary failures.

Full detailed changelog is in CHANGELOG.md
