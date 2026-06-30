# Texture Tool Inventory

This skill is tool-source agnostic. The repository includes a portable binary subset under `vendor-tools/texture-compression`, tracked by Git LFS. Provenance is recorded in `vendor-tools/SOURCES.md`.

## Candidate Tools

| Capability | Candidate executable | Common source-relative paths |
| --- | --- | --- |
| ASTC encode | `astcenc.exe` | `astc-encoder\astcenc.exe`, `mali_win32\astcenc.exe` |
| ETC encode | `etcpack.exe` | `mali_win32\etcpack.exe` |
| Texture convert/composite | `convert.exe`, `composite.exe` | `mali_win32\convert.exe`, `mali_win32\composite.exe` |
| PVRTC/PVR/KTX workflows | `PVRTexToolCLI.exe`, `compare.exe` | `PVRTexTool_win32\PVRTexToolCLI.exe`, `PVRTexTool_win32\compare.exe` |
| WebP encode/decode | `cwebp.exe`, `dwebp.exe` | `libwebp_win32\bin\cwebp.exe`, `libwebp_win32\bin\dwebp.exe` |
| WebP inspect/mux | `webpinfo.exe`, `webpmux.exe` | `libwebp_win32\bin\webpinfo.exe`, `libwebp_win32\bin\webpmux.exe` |

## Search Roots

The helper script searches in this order:

1. Repository-local `vendor-tools\texture-compression`
2. `TEXTURE_TOOLCHAIN_ROOT`
3. `AI_SKILL_LAB_TOOL_ROOT`
4. `VENDOR_TOOLS_ROOT`

## Vendoring Rule

Only add more tools when the workflow is repeated and the imported subset is minimal. Use Git LFS for binaries, archives, textures, and generated fixtures.
