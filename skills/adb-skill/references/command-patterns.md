# Command Patterns

Use these patterns as starting points. Always include `-s <serial>` when more than one device is attached.

## Read-Only

List devices:

```powershell
adb devices -l
```

Basic device properties:

```powershell
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
```

Package listing:

```powershell
adb shell pm list packages
adb shell pm path <package.name>
```

Logcat to file:

```powershell
adb logcat -v threadtime -d > logs/logcat.txt
adb logcat -v threadtime Unity:D ActivityManager:I *:S > logs/filtered-logcat.txt
```

Dumpsys:

```powershell
adb shell dumpsys activity activities
adb shell dumpsys package <package.name>
adb shell dumpsys meminfo <package.name>
```

Screenshot:

```powershell
adb exec-out screencap -p > captures/screen.png
```

Screen recording:

```powershell
adb shell screenrecord /sdcard/capture.mp4
adb pull /sdcard/capture.mp4 captures/capture.mp4
```

## State-Changing

Install APK:

```powershell
adb install -r path/to/app.apk
```

Uninstall package:

```powershell
adb uninstall <package.name>
```

Clear app data:

```powershell
adb shell pm clear <package.name>
```

Push file:

```powershell
adb push local.file /sdcard/Download/local.file
```

Force-stop package:

```powershell
adb shell am force-stop <package.name>
```

## Destructive Or High-Risk

Do not execute these without explicit user confirmation:

```powershell
fastboot flash <partition> <image>
fastboot erase <partition>
fastboot flashing unlock
fastboot oem <command>
adb shell reboot bootloader
adb shell recovery --wipe_data
```

Report the exact device serial, partition, file path, and expected rollback path before running high-risk commands.
