# GPU shader 工具来源与平台策略

## 工具表

| 工具 | 主要用途 | 首选来源 | 备注 |
| --- | --- | --- | --- |
| DXC (`dxc`) | HLSL 编译、DXIL/DXBC container dump、DXIL 反汇编 | https://github.com/microsoft/DirectXShaderCompiler | Windows/Linux release 有二进制资产；macOS 当前按源码构建或可信包管理器处理。 |
| SPIRV-Cross (`spirv-cross`) | SPIR-V reflection、SPIR-V -> HLSL/GLSL/MSL | https://github.com/KhronosGroup/SPIRV-Cross | GitHub release 偏旧；macOS/Linux 常用包管理器或 Vulkan SDK/源码构建。 |
| glslang (`glslangValidator`) | GLSL/HLSL -> SPIR-V、前端验证 | https://github.com/KhronosGroup/glslang | 二进制通常随 Vulkan SDK 提供：https://vulkan.lunarg.com/sdk/home |
| SPIRV-Tools (`spirv-dis`, `spirv-val`, `spirv-opt`) | SPIR-V 验证、反汇编、优化、汇编 | https://github.com/KhronosGroup/SPIRV-Tools | 二进制通常随 Vulkan SDK 提供：https://vulkan.lunarg.com/sdk/home |
| dxil-spirv | DXIL -> SPIR-V | https://github.com/HansKristian-Work/dxil-spirv | 当前无 GitHub release/tag；按源码构建依赖处理。 |
| ShaderConductor | 可选多后端转换包装 | https://github.com/microsoft/ShaderConductor | 可作为辅助，不能替代原始 disassembly 证据。 |

## 平台策略

### Windows

1. 优先使用仓库 `vendor-tools/gpu-shader-toolkit/` 下登记或随仓库携带的工具。
2. dxc 的 Windows 最小可运行集是 `dxc.exe`、`dxcompiler.dll`、`dxil.dll`；不要提交 release zip、`inc/`、`lib/` 或其它架构目录。
3. dxc 缺失时，可登记 Windows SDK 自带版本：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/setup_shader_tools.py register-windows-sdk-dxc
   ```
4. dxc 官方 release 网络可用时，使用：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/setup_shader_tools.py install --tool dxc
   ```
5. SPIR-V 工具建议安装 Vulkan SDK，或把包管理器/源码构建出的 exe 加到 PATH。

### macOS

1. 优先用 Homebrew/Vulkan SDK 准备 SPIR-V 工具：
   ```bash
   brew install spirv-cross
   ```
2. `glslangValidator` 和 `spirv-*` 可通过 Vulkan SDK 或包管理器提供。
3. dxc 若没有官方 macOS release 二进制，不要写死假路径；按源码构建或可信包管理器安装后让 wrapper 从 PATH 解析。

### Linux

1. dxc 可使用 GitHub Linux release asset。
2. SPIR-V 工具可用 distro package、Vulkan SDK 或源码构建。

## 更新流程

1. 打开 `scripts/tool_manifest.json`，查看每个工具的 `homepage`、`latest_release_api`、`latest_checked_tag`。
2. 用 GitHub API 或 release 页面核对新版本：
   ```powershell
   python - <<'PY'
   import json, urllib.request
   url = "https://api.github.com/repos/microsoft/DirectXShaderCompiler/releases/latest"
   print(json.load(urllib.request.urlopen(url))["tag_name"])
   PY
   ```
3. 更新 `latest_checked_tag`、`latest_checked_url` 和 asset pattern。
4. 重新运行安装脚本并验证：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py list
   ```

## 证据记录模板

```text
Tool: dxc
Version: <dxc -help 或可执行文件版本>
Source: <manifest url 或本地 SDK>
Command: dxc -dumpbin -Fc out.asm.txt input.dxil
Input: <path>, sha256=<hash>
Output: <path>
Conclusion: <只写从输出直接支持的结论>
Boundary: <未能证明的部分>
```
