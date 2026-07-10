---
name: unity-global-installer
description: Cross-platform workflow for installing, repairing, and validating global Unity Editor modules when Unity Hub fails. Use when a user asks to install or fix Unity modules outside a project on Windows, macOS, or Linux; diagnose Hub download failures, Unity CDN redirects, mirror 404s, permissions, or corrupt module state; install or repair modules such as Android, iOS, WebGL, Dedicated Server, Windows/Mac/Linux Build Support, tvOS, visionOS, UWP, documentation, or language packs; compare module metadata between installed Editors; safely reuse compatible module payloads; update modules.json selected state; or verify that a target platform actually loads through Unity batchmode.
---

# Unity Global Installer

## 定位

这是 Unity Hub/Editor 全局模块安装修复 skill。它不绑定某个项目，也不绑定 Android。Android、iOS、WebGL、Dedicated Server、Windows/Mac/Linux Build Support 等都按同一套原则处理：从目标 Editor 的 `modules.json` 获取模块真相，优先安装目标版本的官方模块包，最后用 Unity batchmode 验证目标平台能真实加载。

主工具是跨平台 Python：

```bash
python scripts/unity_global_installer.py list-editors
```

旧的“某次 Android 事故”只保留为一个经验模板：Android 可能还有 SDK/NDK/OpenJDK 子模块，但这不是 skill 的边界。

## 通用流程

1. 先确认现场边界。若 cwd 是仓库，运行 `git status --short`，后续只改 Unity 安装目录、下载目录和临时目录。
2. 发现目标 Editor：

   ```bash
   python scripts/unity_global_installer.py list-editors
   ```

3. 列出目标 Editor 支持的模块 ID。不要猜 `android`、`ios`、`webgl`、`server` 的名字，先从本机 `modules.json` 查：

   ```bash
   python scripts/unity_global_installer.py list-modules --editor-version 6000.5.0f1
   python scripts/unity_global_installer.py list-modules --editor-version 6000.5.0f1 --module-id webgl
   ```

4. 检查目标模块及其子模块的 URL、目标目录和 selected 状态：

   ```bash
   python scripts/unity_global_installer.py inspect-module --editor-version 6000.5.0f1 --module-id android --include-children
   python scripts/unity_global_installer.py inspect-module --editor-version 6000.5.0f1 --module-id webgl
   ```

5. 测试下载链路。若被重定向到错误镜像或 404，换网络/代理后重测同一个 URL：

   ```bash
   python scripts/unity_global_installer.py test-url --editor-version 6000.5.0f1 --module-id android
   python scripts/unity_global_installer.py test-url --editor-version 6000.5.0f1 --module-id android --proxy http://127.0.0.1:7896
   ```

6. 下载或安装模块。默认 dry-run；写入系统目录必须加 `--apply`，并按平台用管理员权限或 `sudo`：

   ```bash
   python scripts/unity_global_installer.py download-module --editor-version 6000.5.0f1 --module-id webgl
   python scripts/unity_global_installer.py install-module --editor-version 6000.5.0f1 --module-id webgl --apply
   ```

7. 必要时标记模块 selected。只在实际 payload 已安装或确认 Hub 状态损坏时使用：

   ```bash
   python scripts/unity_global_installer.py mark-selected --editor-version 6000.5.0f1 --module-id webgl --include-children --apply
   ```

8. 用目标平台做真实加载验证：

   ```bash
   python scripts/unity_global_installer.py validate-build-target --editor-version 6000.5.0f1 --build-target WebGL
   python scripts/unity_global_installer.py validate-build-target --editor-version 6000.5.0f1 --build-target iOS
   python scripts/unity_global_installer.py validate-build-target --editor-version 6000.5.0f1 --build-target Android
   ```

## 平台差异

- Windows Hub Editor 常见根目录：`C:\Program Files\Unity\Hub\Editor\<version>`。Unity 模块主安装器通常是 `.exe`，脚本用 `/S /D=<editor>` 计划或执行。
- macOS Hub Editor 常见根目录：`/Applications/Unity/Hub/Editor/<version>`。模块主安装器通常是 `.pkg`，脚本用 `sudo installer -pkg <pkg> -target /` 计划或执行。
- Linux Hub Editor 常见根目录：`~/Unity/Hub/Editor/<version>`、`~/.local/share/Unity/Hub/Editor/<version>` 或 `/opt/Unity/Hub/Editor/<version>`。遇到未知 `.tar.xz`、`.sh` 或自定义包时，脚本先给出下载与模块元数据，不强行猜解压规则。
- 可用 `UNITY_EDITOR_ROOT`、`UNITY_HUB_EDITOR_ROOT` 或 `--editor-root` 指向非默认安装根。

## 模块通用策略

- 以目标版本 `modules.json` 为准。不要从网页、记忆或另一个版本猜模块 ID、URL、destination。
- 优先安装目标版本官方模块包。跨版本直接复制 Unity 平台扩展主体是高风险行为。
- 对任意模块，如果想从 donor Editor 复用 payload，先比较 URL：

  ```bash
  python scripts/unity_global_installer.py compare-modules --editor-version 6000.5.0f1 --donor-editor-version 6000.4.10f1 --module-id android --include-children
  ```

- 只有 URL 完全一致的模块 payload 才默认允许复制。版本特定 URL 不一致时，脚本会跳过该模块并继续处理其它子模块；除非显式 `--allow-different-url`，这种覆盖必须在回复里标成高风险。

  ```bash
  python scripts/unity_global_installer.py copy-module-payloads --editor-version 6000.5.0f1 --donor-editor-version 6000.4.10f1 --module-id android --include-children --apply
  ```

## 验收标准

至少满足这些条件才宣布修复完成：

- 模块下载来源来自目标 Editor 的 `modules.json`。
- 安装或复制动作有明确目标目录和备份/回滚边界。
- `inspect-module` 显示目标 module 或必要 child module 的 destination 已存在。
- `modules.json` selected 状态与实际安装状态一致。
- `validate-build-target` 能让 Unity batchmode 以目标 `-buildTarget` 启动并退出码为 0。
- 日志不能出现 `Could not add platformSupportModule`、`VTable setup ... failed` 或平台模块加载失败。

## Android 特化检查

Android 只是一个复杂模块例子。除了通用验收，还检查：

- `AndroidPlayer/UnityEditor.Android.Extensions.dll` 来自目标版本官方模块。
- `SDK/platform-tools/adb`、`SDK/build-tools/*/aapt2`、`SDK/platforms/android-*/android.jar`、`NDK/source.properties`、`OpenJDK/bin/java` 存在。
- 若从 donor 复制 `SDK`、`NDK`、`OpenJDK`，必须先用 `compare-modules --include-children` 确认对应子模块 URL 一致。

## Dedicated Server / DS 说明

Dedicated Server 常表现为某个平台 Build Support 的 server 子模块或 standalone 子目标。不要猜 `ds` 是模块 ID；先 `list-modules --module-id server`、`list-modules --module-id dedicated`、`list-modules --module-id linux` 查本机目标版本。验证时可传额外 Unity 参数，例如：

```bash
python scripts/unity_global_installer.py validate-build-target --editor-version 6000.5.0f1 --build-target StandaloneLinux64 --unity-arg -standaloneBuildSubtarget --unity-arg Server
```

## 输出边界

若只是下载成功，不等于安装成功。若只是 Hub UI 显示 selected，不等于 Unity 能加载。最终回复必须说明：目标 Editor、模块 ID、安装来源、写入位置、验证命令、日志结论、未完成边界。
