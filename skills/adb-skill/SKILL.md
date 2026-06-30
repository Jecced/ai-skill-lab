---
name: adb-skill
description: Use Android SDK Platform-Tools safely and repeatably through adb, fastboot, sqlite3, etc1tool, and related command-line utilities. Use when inspecting connected Android devices, checking adb or fastboot availability, installing or uninstalling APKs, collecting logcat, bugreport, dumpsys, screenshots, screen recordings, pulling or pushing files, querying packages, diagnosing Android app/device state, or planning dangerous fastboot commands with explicit safety gates.
---

# ADB Skill

## Overview

Use this skill for Android device CLI work with repository-local platform-tools first, then environment overrides. Prefer read-only inspection and command planning before changing device state.

## Quick Workflow

1. Discover platform-tools:

   ```powershell
   python scripts/adb_tool.py discover
   ```

   Override with `ADB_PLATFORM_TOOLS_ROOT`, `ANDROID_PLATFORM_TOOLS_ROOT`, or `ANDROID_HOME` only when intentionally using a local Android SDK.

2. Check tool versions:

   ```powershell
   python scripts/adb_tool.py version
   ```

3. List connected devices before any device-specific command:

   ```powershell
   python scripts/adb_tool.py devices
   ```

4. Generate command plans for common work:

   ```powershell
   python scripts/adb_tool.py plan-logcat --output logs/app.log --tag Unity --tag ActivityManager
   python scripts/adb_tool.py plan-screenshot --output captures/screen.png
   python scripts/adb_tool.py plan-install --apk build/app-debug.apk
   ```

5. Execute planned commands only after confirming the target serial, output path, and side effects.

## Safety Rules

- Treat `adb devices`, `adb shell getprop`, `adb shell dumpsys`, `adb logcat`, `adb bugreport`, screenshots, screen recordings, and file pulls as low-risk read-only operations.
- Treat `adb install`, `adb uninstall`, `adb push`, `adb shell am force-stop`, `adb shell pm clear`, and settings writes as state-changing operations. Call out the target package/device explicitly.
- Treat `fastboot flash`, `fastboot erase`, `fastboot oem`, bootloader unlock, factory reset, and partition writes as destructive. Do not run them unless the user explicitly asks for that exact operation and accepts the device risk.
- Do not assume there is only one device. If multiple devices are attached, require or infer an explicit `--serial` before executing.
- Do not collect logs or bugreports silently when privacy may matter; report that these can contain package names, file paths, account identifiers, URLs, and device details.

## References

- Read `references/platform-tools.md` when updating the vendored tools, checking provenance, or deciding which binaries belong in `vendor-tools/adb/platform-tools`.
- Read `references/command-patterns.md` for common ADB command patterns and risk labels.
