---
name: gpu-shader-toolkit
description: Cross-platform GPU shader binary inspection and reverse-engineering workflow with bundled setup/call wrappers for DXC, SPIRV-Cross, glslang, SPIRV-Tools, dxil-spirv, and related GitHub/open-source tools. Use when analyzing DXIL/DXBC/SPIR-V/MSL/HLSL shader blobs, PIX/RenderDoc/GPA exported shaders, resource binding tables, disassembly, decompilation, shader cross-compilation, or when installing/updating local shader toolchains on Windows/macOS/Linux.
---

# GPU Shader Toolkit

用这个 skill 时，目标是把 shader 二进制分析变成可重复流程，而不是临时手敲 `dxc`/`spirv-cross` 命令。

## 快速流程

1. 先确认任务对象：DXIL/DXBC、SPIR-V、HLSL/GLSL/MSL 源码，或 PIX/RenderDoc/GPA 导出的 shader blob。
2. 读取 `references/tool-sources.md`，只加载和当前平台/格式相关的工具来源。
3. 用 `scripts/gpu_shader_tool.py list` 查看可调用工具；缺工具时用 `scripts/setup_shader_tools.py` 下载、登记或打印平台安装建议。
4. 对 DXIL/DXBC，优先用 dxc：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py dxc-dumpbin shader.dxil -o shader.asm.txt
   ```
5. 对 SPIR-V，优先用 SPIRV-Tools 验证/反汇编，再用 SPIRV-Cross 生成 reflection 或目标语言：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py spirv-val shader.spv
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py spirv-cross shader.spv --reflect -o shader.reflect.json
   ```
6. 把每次使用的工具版本、命令、输入 hash、输出路径写入项目文档；不要只给结论。

## 工具策略

- Windows：优先使用仓库 `vendor-tools/gpu-shader-toolkit/` 下的本地工具；缺 dxc 时允许 fallback 到 Windows SDK `dxc.exe`。
- macOS：优先使用 Homebrew/Vulkan SDK 安装的 `spirv-cross`、`glslangValidator`、`spirv-*`；dxc 若没有官方 release 二进制，按来源文档走源码构建或包管理器。
- Linux：优先使用 DXC Linux release、包管理器或 Vulkan SDK。
- GitHub release 有稳定二进制时用下载脚本固定版本；只有源码 release 时不要假装已安装，记录为 source/build dependency。

## 常用资源

- `scripts/tool_manifest.json`：工具来源、release API、asset pattern、安装提示和更新链接。
- `scripts/setup_shader_tools.py`：下载 GitHub release 资产、复制 Windows SDK dxc、写入本地 toolchain。
- `scripts/gpu_shader_tool.py`：统一调用 dxc / SPIRV-Cross / glslang / SPIRV-Tools / dxil-spirv。
- `references/tool-sources.md`：工具选择、官方链接、平台差异、更新流程。
- `references/workflows.md`：DXIL、SPIR-V、PIX C++ export 等常见分析工作流。

## 约束

- 第三方二进制放在仓库级 `vendor-tools/gpu-shader-toolkit/`，来源和更新方式记录在 manifest 与 `vendor-tools/SOURCES.md`。
- 工具输出是证据，不是结论。命名 shader 语义时仍要结合 PSO、root signature、descriptor、resource 格式、命令上下文和资源内容。
- 自动反编译 HLSL/GLSL/MSL 只作为辅助，最终以原始 disassembly 和绑定证据为准。
