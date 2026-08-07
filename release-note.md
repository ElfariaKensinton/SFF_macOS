SteaMidra v6.6.3

What's new:

### New features

* Added a new **Linux Guide** tab to the sidebar, available only on Linux systems. It includes a complete SLSsteam setup walkthrough covering prerequisites, SteamOS and Steam Deck SafeMode warnings, Gaming Mode configuration, backup instructions, troubleshooting steps, and helpful community resources.
* Added a **SteamOS first-launch popup** for Linux users. The one-time notice explains the required `sudo steamos-readonly disable` step, SafeMode requirements, and Gaming Mode setup. Users can open the Linux Guide directly from the popup.

### Fixes

* Fixed multiple **bridge runtime crashes** caused by missing references:

  * Added missing `_UNSAFE_FILENAME_RE` import for bulk imports.
  * Added missing `_fetch_steam_image_urls` import for library images.
  * Fixed Store cache timestamp resetting by correctly referencing the Store bridge module namespace.
* Fixed several **SLSsteam YAML corruption issues**:

  * YAML sections with inline comments are now handled correctly.
  * Duplicate sections are no longer created.
  * AdditionalApps entries are inserted correctly on their own lines.
  * Backup files now always overwrite correctly.
  * Atomic writes now force data to disk before renaming, preventing empty configuration files after crashes.
  * Commented-out configuration keys are no longer incorrectly treated as active settings.
  * Removed a duplicate write path that bypassed the atomic save system.
* Fixed the **Ryuu API key infinite prompt loop**. Premium keys saved through Settings are now detected correctly when no Reseller key exists. Failed authentication now clears both key types instead of repeatedly asking for credentials.

### Improvements

* Provider contribution features are now enabled by default:

  * `PROVIDER_CONTRIBUTE_KEYS` enabled by default.
  * `PROVIDER_ENRICH_STEAM_METADATA` enabled by default.
  * Contribution interval reduced from 24 hours to 3 hours.
  * First contribution now starts 3 seconds after launch.
  * Existing users are automatically migrated through the settings version update.
* Reduced Steam client log noise by removing unnecessary per-app debug messages during library scans. Only useful timing and cache information remains.

Full detailed changelog is in CHANGELOG.md
