---
name: gpu-shader-toolkit
description: Cross-platform GPU shader binary inspection, reverse-engineering, and captured-shader porting workflow with wrappers for DXC, SPIRV-Cross, glslang, SPIRV-Tools, dxil-spirv, and related open-source tools. Use when analyzing DXIL/DXBC/SPIR-V/MSL/HLSL blobs from PIX, RenderDoc, GPA, or engine builds; reconstructing resource bindings and constant-buffer semantics; preserving sampler and packed-format evidence; cross-compiling captured shaders into another API or engine; recording translation deviations; or installing/updating local shader toolchains on Windows/macOS/Linux.
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
7. 从截帧移植 shader 时，先读 `references/captured-shader-porting.md`，保持原始 binary、disassembly/reflection、translated source 和 engine adapter 四层分离。
8. 为移植产物生成并校验 manifest：

   ```powershell
   python skills/gpu-shader-toolkit/scripts/shader_port_manifest.py create `
     --source shader.spv --encoding SPIR-V --stage ps --entry main `
     --disassembly shader.spvasm --reflection shader.reflect.json `
     --translated shader.hlsl --output shader.port.json
   python skills/gpu-shader-toolkit/scripts/shader_port_manifest.py verify shader.port.json
   ```

## 工具策略

- Windows：优先使用仓库 `vendor-tools/gpu-shader-toolkit/` 下的本地工具。内置 SPIR-V 四个 CLI，不依赖 RenderDoc 安装；缺 dxc 时允许 fallback 到 Windows SDK `dxc.exe`。
- macOS：优先使用 Homebrew/Vulkan SDK 安装的 `spirv-cross`、`glslangValidator`、`spirv-*`；dxc 若没有官方 release 二进制，按来源文档走源码构建或包管理器。
- Linux：优先使用 DXC Linux release、包管理器或 Vulkan SDK。
- GitHub release 有稳定二进制时用下载脚本固定版本；只有源码 release 时不要假装已安装，记录为 source/build dependency。

## 常用资源

- `scripts/tool_manifest.json`：工具来源、release API、asset pattern、安装提示和更新链接。
- `scripts/setup_shader_tools.py`：下载 GitHub release 资产、复制 Windows SDK dxc、写入本地 toolchain。
- `scripts/gpu_shader_tool.py`：统一调用 dxc / SPIRV-Cross / glslang / SPIRV-Tools / dxil-spirv。
- `references/tool-sources.md`：工具选择、官方链接、平台差异、更新流程。
- `references/workflows.md`：DXIL、SPIR-V、PIX C++ export 等常见分析工作流。
- `references/captured-shader-porting.md`：常量槽、sampler、packed format、坐标系和跨 API/引擎移植契约。
- `scripts/shader_port_manifest.py`：记录原始与派生产物 hash、工具/命令和不可避免的 translation deviation。

## 约束

- 第三方二进制放在仓库级 `vendor-tools/gpu-shader-toolkit/`，来源和更新方式记录在 manifest 与 `vendor-tools/SOURCES.md`。
- 工具输出是证据，不是结论。命名 shader 语义时仍要结合 PSO、root signature、descriptor、resource 格式、命令上下文和资源内容。
- 自动反编译 HLSL/GLSL/MSL 只作为辅助，最终以原始 disassembly 和绑定证据为准。
- 不把反编译变量名、单个常量槽或旧 capture 的资源 ID 当成跨帧稳定语义。把语义回连到 byte offset、load/use、descriptor、资源格式和受控对比。
- 不覆盖原始 shader blob。所有 sampler、控制流、packed format、depth view 和坐标修正都写入 port manifest，直到运行时验证前保持 `inferred` 或 `unresolved`。
