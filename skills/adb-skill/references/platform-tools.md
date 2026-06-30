# Platform-Tools

The default bundled tools live at:

```text
vendor-tools/adb/platform-tools
```

Discovery order:

1. Repository-local `vendor-tools/adb/platform-tools`.
2. `ADB_PLATFORM_TOOLS_ROOT`.
3. `ANDROID_PLATFORM_TOOLS_ROOT`.
4. `$ANDROID_HOME/platform-tools`.
5. `$ANDROID_SDK_ROOT/platform-tools`.
6. `PATH`.

## Bundled Version

Current Windows bundle:

```text
Pkg.Revision=37.0.0
adb Version 37.0.0-14910828
Downloaded from https://dl.google.com/android/repository/platform-tools-latest-windows.zip
SHA256 4FE305812DB074CEA32903A489D061EB4454CBC90A49E8FEA677F4B7AF764918
```

Official release notes:

```text
https://developer.android.com/tools/releases/platform-tools
```

## Included Files

Keep the whole official `platform-tools` folder unless there is a strong reason to trim. Some commands rely on sibling DLLs or config files.

Core files:

- `adb.exe`
- `fastboot.exe`
- `AdbWinApi.dll`
- `AdbWinUsbApi.dll`
- `libwinpthread-1.dll`
- `sqlite3.exe`
- `etc1tool.exe`
- `hprof-conv.exe`
- `source.properties`
- `NOTICE.txt`

Filesystem helpers from the official package:

- `make_f2fs.exe`
- `make_f2fs_casefold.exe`
- `mke2fs.exe`
- `mke2fs.conf`

## Update Checklist

1. Check the official release notes for the latest version.
2. Download `platform-tools-latest-windows.zip` from the official Google URL.
3. Verify `source.properties` and `adb --version`.
4. Record the ZIP SHA256 in `vendor-tools/SOURCES.md`.
5. Replace `vendor-tools/adb/platform-tools` with the extracted official folder.
6. Run:

   ```powershell
   python skills/adb-skill/scripts/adb_tool.py discover
   python skills/adb-skill/scripts/adb_tool.py version
   git lfs status
   ```
