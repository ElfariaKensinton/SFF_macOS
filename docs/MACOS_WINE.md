# SteaMidra on Wine/macOS

This fork targets SteaMidra running under Wine/CrossOver on macOS rather than a native macOS build.

The macOS/Wine path is based on the approach documented in the Reddit discussion: [SteaMidra Solution for Crossover on macOS](https://www.reddit.com/r/PiracyNoRestrictions/comments/1u9v014/steamidra_solution_for_crossover_on_macos/).

The fork includes a manual installer workflow and a macOS build patch. After running Auto LC Setup, replace the release `dwmapi.dll` in the Steam folder with the macOS/Wine-compatible build produced by the workflow.
