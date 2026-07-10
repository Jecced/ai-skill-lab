# Shader binary 分析工作流

## DXIL / DXBC

用于 PIX C++ export、RenderDoc 导出、Windows HLSL shader blob。

1. 保存原始 blob，不要只保存反汇编文本。
2. 用 dxc dump：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py dxc-dumpbin PSO_28752_PS.dxil -o PSO_28752_PS.asm.txt
   ```
3. 先看这些区块：
   - input/output signature
   - resource table
   - root/cbuffer load
   - `createHandleFromHeap` / descriptor index 来源
   - `TextureLoad` / `TextureStore` / `sample`
   - `SV_Target` / UAV store
   - `NumThreads`
4. 结论必须回连到命令上下文：PSO、root signature、descriptor table、RT/UAV/SRV resource 格式、draw/dispatch 参数。

## SPIR-V

1. 先验证：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py spirv-val shader.spv
   ```
2. 再反汇编：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py spirv-dis shader.spv -o shader.spvasm
   ```
3. 需要资源 reflection 时：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py spirv-cross shader.spv --reflect -o shader.reflect.json
   ```
4. 需要目标语言可读化时，使用 `--hlsl`、`--msl`、`--glsl <version>`；生成代码只作为辅助，不替代原始 SPIR-V 证据。

## HLSL / GLSL 源码验证

1. 对 HLSL，优先 dxc，明确 target/profile 和 entry：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py dxc-compile shader.hlsl -T cs_6_6 -E CSMain -o shader.dxil
   ```
2. 对 GLSL/HLSL -> SPIR-V，使用 `glslangValidator`：
   ```powershell
   python skills/gpu-shader-toolkit/scripts/gpu_shader_tool.py glslang -- -V shader.comp -o shader.spv
   ```

## PIX C++ export 中的 shader

1. 先索引 C++ export，定位 PSO 使用点和 `resources.bin` 读取顺序。
2. 从 PSO chunk 提取 DXIL blob，保留 `PSO_<id>_<stage>.dxil`。
3. 用本 skill 的 dxc wrapper 生成 `Disasm/PSO_<id>_<stage>.asm.txt`。
4. 结合 `CreatePSOs.cpp`、`CommandLists_*.cpp`、`Descriptors_*.cpp`、resource 创建代码闭合语义。
5. 如果需要进一步可读化，可尝试 DXIL -> SPIR-V -> SPIRV-Cross，但只标为辅助推断。

## RenderDoc / GPA captured shader 移植

1. 保留 capture 导出的原始 shader binary、entry point、stage、encoding 和 hash。
2. 保存 disassembly 与 reflection，再生成目标语言源码；不要只保留 cross-compiled HLSL/MSL/GLSL。
3. 把 shader 绑定回 capture 的 pipeline、descriptor、sampler、RT/UAV 格式和常量 buffer byte range。
4. 读取 `captured-shader-porting.md`，建立常量语义表和 translation deviation 表。
5. 用 `shader_port_manifest.py create` 记录 source、disassembly、reflection、translated source、engine adapter、工具版本和命令。
6. 在目标引擎编译后运行 `shader_port_manifest.py verify`，并用中间 RT/数值对比证明 translated path，而不是显示一张 captured reference。

## 常见误区

- `dxc -dumpbin` 的输出不能单独证明某个 texture 的业务含义；只能证明 shader 如何访问。
- 反编译代码变量名通常不可信；可信的是 binding、格式、访问模式、数学结构和命令上下文。
- SPIRV-Cross 输出的 HLSL/MSL 可能重排表达式；需要回到原始 disassembly 对关键结论做核对。
- 不要从变量名或某次抓帧里的 `cNN/mNN` 名称直接命名光照、相机或时间语义；检查 byte offset、实际 load/use 和跨帧数值变化。
- 不要用全局 UV flip 修复所有 API 差异；raw texture、generated RT、scene depth、view ray 和 final display 必须分层验证。
- target API 不支持原 packed format 时，优先保留 raw bits 并显式解码，不要静默改成更高精度或不同色彩空间。
- macOS/Windows 工具版本可能不同；跨平台结论要记录工具版本。
