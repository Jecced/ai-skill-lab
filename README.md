# ai-skill-lab

通用 AI Skill 沉淀仓库。

目标是维护一套平台无关的 skill 源资产，再按需适配到 Codex、Claude、Trae 等主流 AI 工具。核心知识和流程尽量只维护一份，平台差异放到适配层。

## Repository Layout

- `skills/`: 平台无关的 skill 源内容，优先沉淀稳定、重复、可验证的工作流。
- `targets/`: 面向不同 AI 工具的适配输出，例如 `codex`、`claude`、`trae`。
- `vendor-tools/`: 必须随仓库保存的第三方工具或离线工具链。大文件和二进制文件由 Git LFS 管理；默认 skill 应优先使用这里的可携带工具。
- `docs/`: 盘点、设计记录、迁移说明和工具分类判断。

## Skill Rule

不要把一个工具目录机械包装成一个 skill。优先把 skill 设计成可复用工作流：

- `SKILL.md` 写触发场景、判断流程和执行步骤。
- `references/` 放工具参数、版本差异、常见错误和验证样例。
- `scripts/` 放稳定的封装脚本。
- `assets/` 或 `vendor-tools/` 才放必须随 skill 使用的二进制资产。

如果工具来自某个 SDK、Editor、引擎或本机安装目录，默认只把它当作来源快照：先记录来源、版本、许可证风险和本地路径。确认有通用复用价值后，再按最小可用子集分批复制进 `vendor-tools/`。

## Current Skills

平台支持说明：

- `Win`: 仓库已内置 Windows 二进制工具，`git lfs pull` 后可直接执行。
- `Mac`: 仓库已为部分 skill 内置 macOS 二进制工具；未覆盖的工具仍可通过环境变量指向本机工具。

macOS 工具架构不是完全一致：部分工具是 universal，部分 `mali_darwin` / `PVRTexTool_darwin` 工具是 x86_64，在 Apple Silicon 上可能需要 Rosetta。

| Skill | 作用 | 核心功能 | Win | Mac | 可用场景 |
| --- | --- | --- | --- | --- | --- |
| `skills/texture-compression-toolchain` | 通用纹理压缩与图片格式转换工具链。 | 发现仓库内纹理工具；根据目标平台选择 ASTC、ETC、PVRTC、WebP 等格式；生成 dry-run 命令；执行前规划批处理；输出验证清单；记录压缩参数和工具来源。 | 支持，仓库内已带 `astcenc`、Mali `etcpack/convert/composite`、`PVRTexToolCLI`、`cwebp/dwebp/webpinfo/webpmux` 等 Windows 工具。 | 支持主要编码流程，仓库内已带 macOS `astcenc`、Mali `etcpack/convert/composite`、`PVRTexToolCLI/compare`、`cwebp`；`dwebp/webpinfo/webpmux` 当前需本机工具补齐。 | 游戏/渲染项目纹理压缩；移动端纹理格式选择；WebP 资源体积优化；UI/法线/Mask 贴图压缩前检查；跨机器复现实验参数。 |
| `skills/environment-map-toolchain` | 通用环境贴图、Cubemap、IBL 预处理工具链。 | 发现仓库内环境贴图工具；规划 HDR/LDR、equirect/cubemap/cross 输入处理；生成 `cmft` dry-run 命令；规划 radiance/irradiance 输出；提供 face orientation、mip、曝光、接缝验证清单。 | 支持，仓库内已带 `cmftRelease64.exe` Windows 工具。 | 支持，仓库内已带 macOS `cmftRelease64`。 | HDRI 转 Cubemap；IBL specular radiance 预过滤；irradiance/漫反射环境光输入生成；skybox/reflection probe 资源预处理；渲染实验资产复现。 |
| `skills/gpu-shader-toolkit` | 通用 GPU shader 二进制检查、反汇编、交叉编译与证据记录工具链。 | 统一发现和调用 DXC、SPIRV-Cross、glslang、SPIRV-Tools、dxil-spirv；支持 DXIL/DXBC dump、SPIR-V 验证/反汇编/reflection、HLSL 编译和工具版本记录。 | 支持，仓库内已带 DXC Windows 最小运行集 `dxc.exe/dxcompiler.dll/dxil.dll`；其它工具可从 PATH、Vulkan SDK 或下载脚本补齐。 | 流程可用；可使用 Homebrew/Vulkan SDK/本机工具，当前未内置 macOS 二进制。 | 分析 PIX/RenderDoc/GPA 导出的 shader；检查 DXIL/DXBC/SPIR-V；对照 resource binding 和 root signature；复现实验 shader 编译参数。 |
| `skills/pix-cpp-export-toolkit` | 通用 PIX on Windows C++ 导出索引与逆向证据链工作流。 | 验证导出结构；重建 `resourceReader` 读流；索引 PSO、shader bytecode 读取、CommandLists 命令事件、Dispatch/ExecuteIndirect/DrawIndexedInstanced 候选；输出 Markdown/JSON 报告。 | 支持，PIX C++ 导出来源是 Windows；索引脚本是 Python，无额外二进制依赖。 | 可分析已经复制过来的 C++ 导出文件；PIX 导出本身仍依赖 Windows/PIX，资源解压或领域提取脚本需另行补齐。 | 将 PIX C++ 导出变成可复查报告；定位渲染/计算 pass 候选；追踪 PSO、root 参数、descriptor、resource id；为项目专用提取脚本提供稳定入口。 |

这些 skill 已尽量携带必要的仓库内二进制工具子集；换电脑后，应优先依赖 `vendor-tools/` 和 `git lfs pull`，不依赖原始安装目录。

## Git LFS

本仓库已经启用 Git LFS，并在 `.gitattributes` 中跟踪常见工具链二进制、压缩包、离线帮助包、图片和纹理资产。

导入大文件前先确认：

```powershell
git lfs install
git lfs track
```

提交前检查：

```powershell
git lfs status
git diff --check
```
