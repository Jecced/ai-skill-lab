# Stream Extraction

Use `scripts/pix_stream_extract.py` after indexing a PIX C++ export and identifying a PSO id, resource id, or replay function worth inspecting.

## Command Shapes

Extract PSO shader bytecode and disassemble when `dxc.exe` is available:

```powershell
python skills/pix-cpp-export-toolkit/scripts/pix_stream_extract.py `
  --pix-dir "<PIX C++ export path>" `
  --pso 28667 `
  --output-dir "<analysis output>"
```

Extract a resource initialization payload:

```powershell
python skills/pix-cpp-export-toolkit/scripts/pix_stream_extract.py `
  --pix-dir "<PIX C++ export path>" `
  --resource 28686 `
  --output-dir "<analysis output>"
```

Extract every compressed read block from a replay function:

```powershell
python skills/pix-cpp-export-toolkit/scripts/pix_stream_extract.py `
  --pix-dir "<PIX C++ export path>" `
  --function CreateAndInitResource_28686 `
  --output-dir "<analysis output>"
```

The tool also accepts `--out-dir` as an alias for `--output-dir`, `--no-disasm` to skip `dxc`, and `--dxc "<path>"` to use a specific compiler binary.

## What The Tool Proves

- `--pso` proves the shader bytecode stored in the replay initialization stream for that PSO. The tool splits stages by the literal stage byte lengths in `CreatePSOs.cpp`.
- `--resource` proves the frame-start initialization payload for `CreateAndInitResource_<id>`.
- `--function` proves the decompressed bytes for each `g_resourceReader->Read` call in that replay function.

The output includes `extraction_manifest.json`; keep it with the extracted blobs so offsets, compressed sizes, and disassembly status remain auditable.

## Boundaries

- `resources.bin` is an XPRESS-compressed sequential stream, not a direct resource table. The extractor reconstructs compressed offsets by walking `FrameResources_000.cpp` call order and every `g_resourceReader->Read` size.
- Resource initialization payloads are frame-start state. Buffers or textures produced later by compute, copy, or render passes can be zero, stale, or unrelated at initialization time. For frame-produced data, trace the producing dispatch/draw, barriers, UAV writes, descriptors, and shader access.
- Texture payloads still need format, row pitch, subresource, and swizzle interpretation from `CapturedAssets.h` or project-specific metadata.
- Shader disassembly is best-effort. If `dxc.exe` is missing or a blob does not start with `DXBC`, keep the raw blob and use another shader tool if appropriate.
