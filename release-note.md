SteaMidra v6.3.5

What's new:

* Right-click “Add to SteaMidra” now works properly. The frozen build was ignoring the `-f` argument, so `.lua`/`.zip` files opened the app but were not imported. Files now forward to a running instance through IPC, and fresh launches process them immediately. Thanks to Lucas559-noob for reporting this.
* Hubcap API key handling is now more reliable. The key no longer silently disappears between restarts, startup preloads the key before store search, and encryption-key mismatch warnings are now logged clearly.
* Hubcap key saving now validates the key format, so random text or full log dumps cannot be saved as an API key.
* Store search no longer crashes on Hubcap game names with em dashes or other Unicode characters.
* Added a Disconnect Hubcap button next to the NSFW toggle. You can drop the Hubcap API connection and fall back to bare Steam search without reloading the app.
* Depot OS dropdowns in the download modals now use SteaMidra’s custom dropdown system, fixing the white-rectangle rendering glitch on dark themes.
* Library drive picker is now wired up with the same dropdown system.
* LC Auto Setup now avoids stale GitHub releases and skips source-code archives when looking for the real DLL archive.
* Missing DLL errors now include the downloaded zip file listing in the logs, making broken release/archive issues much easier to debug.
* Home page yellow hint banner is now collapsed by default to save vertical space. Click the arrow to expand it when needed.
* DLC Unlockers card moved to the bottom next to Quick Tools.
* “Let Updates” renamed to “Auto Update”.
* Crack Files picker now shows the Build ID from crackfiles.json next to each game name, making it easier to match fixes with your installed version.
* Bulk import cancel now reliably hides the progress bar.

Full detailed changelog is in CHANGELOG.md
