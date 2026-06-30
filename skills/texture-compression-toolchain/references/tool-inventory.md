# Texture Tool Inventory

This skill is tool-source agnostic. The repository includes a portable binary subset under `vendor-tools/texture-compression`, tracked by Git LFS. Provenance is recorded in `vendor-tools/SOURCES.md`.

## Candidate Tools

| Capability | Windows paths | macOS paths |
| --- | --- | --- |
| ASTC encode | `astc-encoder\astcenc.exe`, `mali_win32\astcenc.exe` | `macos/astc-encoder/astcenc`, `macos/mali_darwin/astcenc` |
| ETC encode | `mali_win32\etcpack.exe` | `macos/mali_darwin/etcpack` |
| Texture convert/composite | `mali_win32\convert.exe`, `mali_win32\composite.exe` | `macos/mali_darwin/convert`, `macos/mali_darwin/composite` |
| PVRTC/PVR/KTX workflows | `PVRTexTool_win32\PVRTexToolCLI.exe`, `PVRTexTool_win32\compare.exe` | `macos/PVRTexTool_darwin/PVRTexToolCLI`, `macos/PVRTexTool_darwin/compare` |
| WebP encode | `libwebp_win32\bin\cwebp.exe` | `macos/libwebp_darwin/bin/cwebp` |
| WebP decode/inspect/mux | `libwebp_win32\bin\dwebp.exe`, `libwebp_win32\bin\webpinfo.exe`, `libwebp_win32\bin\webpmux.exe` | Not bundled yet; use local `dwebp`, `webpinfo`, or `webpmux` via a configured tool root. |

## Search Roots

The helper script searches in this order:

1. Repository-local `vendor-tools\texture-compression`
2. `TEXTURE_TOOLCHAIN_ROOT`
3. `AI_SKILL_LAB_TOOL_ROOT`
4. `VENDOR_TOOLS_ROOT`

Set `AI_SKILL_LAB_PLATFORM=macos` or `AI_SKILL_LAB_PLATFORM=windows` to simulate platform-specific discovery from another OS.

## Vendoring Rule

Only add more tools when the workflow is repeated and the imported subset is minimal. Use Git LFS for binaries, archives, textures, and generated fixtures.
