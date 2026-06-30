---
name: pix-cpp-export-toolkit
description: Generic PIX on Windows C++ export indexing and reverse-analysis workflow. Use when analyzing PIX C++ replay exports containing CreatePSOs.cpp, CommandLists_*.cpp, FrameResources_000.cpp, CapturedAssets.h, and resources.bin; when reconstructing PSO, Dispatch, ExecuteIndirect, DrawIndexedInstanced, resourceReader read streams, resource offsets, shader bytecode evidence, or when turning a capture into repeatable evidence reports without binding to a specific game or project.
---

# PIX C++ Export Toolkit

Use this skill to turn a PIX on Windows C++ export into a repeatable evidence base. Keep the core workflow domain-neutral: command shape can identify candidates, but business names require evidence from PSO, root parameters, descriptors, resources, shader access, and data samples.

## Quick Workflow

1. Confirm the export contains at least `CreatePSOs.cpp`, `CommandLists_*.cpp`, `FrameResources_000.cpp`, `CapturedAssets.h`, and `resources.bin`.
2. Generate an index before drawing conclusions:

   ```powershell
   python skills/pix-cpp-export-toolkit/scripts/pix_cpp_export_index.py --pix-dir "<PIX C++ export path>"
   ```

3. Read `.pix-analysis/pix-cpp-export-indexes/<label>/pix_cpp_export_index.md` first. Use the JSON next to it for scripting.
4. Treat `Dispatch(32,32,1)`, `Dispatch(1,1,1)`, `ExecuteIndirect`, and `DrawIndexedInstanced` matches as candidates only.
5. When extracting or naming resources, follow the `resourceReader` stream from `FrameResources_000.cpp`; do not infer a `resources.bin` offset by only scanning `CreateAndInitResource_*`.
6. Record conclusions as `verified`, `candidate`, `inferred`, or `missing evidence`.

## Resources

- `scripts/pix_cpp_export_index.py`: indexes required files, reconstructs the `g_resourceReader->Read` stream, summarizes PSOs, scans command events, and writes Markdown/JSON reports.
- `references/pix-cpp-export-structure.md`: explains the core files and why read-stream order matters.
- `references/evidence-workflow.md`: generic evidence closure checklist for naming passes or resources.
- `references/domain-adapter-guide.md`: how to add project-specific semantics without polluting this generic skill.

## Boundaries

- This skill does not require any specific project, game, or renderer.
- PIX event ids, PSO ids, descriptor ids, resource ids, and root offsets can drift between captures. Re-index every new export.
- The indexer does not decompress resource payloads. It gives stable offsets, PSO anchors, and command anchors for follow-up project-specific extraction tools.
- Use `gpu-shader-toolkit` alongside this skill when inspecting DXIL/DXBC/SPIR-V shader bytecode emitted by the export.
