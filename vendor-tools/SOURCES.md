# Vendor Tool Sources

This folder contains portable binary subsets required by repository skills. Binaries are tracked by Git LFS.

## 2026-06-30 Toolchain Seed

Copied from local source snapshot:

`C:\ProgramData\cocos\editors\Creator\3.8.8\resources\tools`

The source path is provenance only. Runtime discovery should use the files under `vendor-tools/` by default.

Copied subsets:

- `texture-compression/astc-encoder/astcenc.exe`
- `texture-compression/mali_win32/*`
- `texture-compression/PVRTexTool_win32/*`
- `texture-compression/libwebp_win32/bin/*`
- `texture-compression/libwebp_win32/Readme.txt`
- `texture-compression/libwebp_win32/Readme-mux.txt`
- `environment-map/cmft/cmftRelease64.exe`

## 2026-06-30 GPU Shader Toolkit Seed

Copied from local GPU shader tool cache:

`D:\dev\self\MangoRenderLab\.codex\skills\gpu-shader-toolkit\tools\win-x64\dxc\v1.9.2602.24\runtime-x64`

Copied subset:

- `gpu-shader-toolkit/dxc/win-x64/v1.9.2602.24/runtime-x64/dxc.exe`
- `gpu-shader-toolkit/dxc/win-x64/v1.9.2602.24/runtime-x64/dxcompiler.dll`
- `gpu-shader-toolkit/dxc/win-x64/v1.9.2602.24/runtime-x64/dxil.dll`

Original upstream: Microsoft DirectXShaderCompiler release `v1.9.2602.24`.

Only the Windows x64 runtime subset was copied. Release archives, headers, libraries, symbols, and other architectures were intentionally left out.

## 2026-06-30 macOS Toolchain Seed

Copied from local source snapshot:

`F:\download\toos\tools`

The source path is provenance only. Runtime discovery should use the files under `vendor-tools/` by default.

Copied subsets:

- `texture-compression/macos/astc-encoder/astcenc`
- `texture-compression/macos/mali_darwin/astcenc`
- `texture-compression/macos/mali_darwin/etcpack`
- `texture-compression/macos/mali_darwin/convert`
- `texture-compression/macos/mali_darwin/composite`
- `texture-compression/macos/PVRTexTool_darwin/PVRTexToolCLI`
- `texture-compression/macos/PVRTexTool_darwin/compare`
- `texture-compression/macos/libwebp_darwin/bin/cwebp`
- `environment-map/macos/cmft/cmftRelease64`

The copied macOS subset intentionally excludes `cmake`, quick-game packaging tools, `node_modules`, headers, libraries, docs, and unrelated native addons.

Observed Mach-O architecture notes:

- `environment-map/macos/cmft/cmftRelease64`: universal `x86_64` + `arm64`.
- `texture-compression/macos/astc-encoder/astcenc`: universal, includes `arm64`.
- `texture-compression/macos/libwebp_darwin/bin/cwebp`: universal `x86_64` + `arm64`.
- `texture-compression/macos/mali_darwin/*`: `x86_64`.
- `texture-compression/macos/PVRTexTool_darwin/*`: `x86_64`.

Review license and redistribution terms before publishing this repository outside a private or internal context.
