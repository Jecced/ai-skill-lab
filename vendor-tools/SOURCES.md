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

Review license and redistribution terms before publishing this repository outside a private or internal context.
