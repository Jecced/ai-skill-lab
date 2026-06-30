---
name: pix-cpp-export-toolkit
description: Generic PIX on Windows .wpix capture and C++ export indexing workflow. Use when given a PIX on Windows capture path or replay export; when calling pixtool to export C++ replay projects, save event lists, save RTV/depth resources, or clarify PIX GUI automation limits; when analyzing exports containing CreatePSOs.cpp, CommandLists_*.cpp, FrameResources_000.cpp, CapturedAssets.h, and resources.bin; when reconstructing PSO, Dispatch, ExecuteIndirect, DrawIndexedInstanced, resourceReader read streams, resource offsets, shader bytecode evidence, or repeatable evidence reports without binding to a specific game or project.
---

# PIX C++ Export Toolkit

Use this skill to turn a PIX on Windows `.wpix` capture or C++ export into a repeatable evidence base. Keep the core workflow domain-neutral: command shape can identify candidates, but business names require evidence from PSO, root parameters, descriptors, resources, shader access, and data samples.

## Quick Workflow

1. If the user provides a `.wpix` path, read `references/pixtool-automation.md`, then plan or run the capture preparation:

   ```powershell
   python skills/pix-cpp-export-toolkit/scripts/pix_wpix_tool.py prepare --capture "<capture.wpix>" --execute
   ```

   Omit `--execute` first when the output path, runtime cost, or `pixtool.exe` location is uncertain.
2. If the user provides an existing C++ export, confirm it contains at least `CreatePSOs.cpp`, `CommandLists_*.cpp`, `FrameResources_000.cpp`, `CapturedAssets.h`, and `resources.bin`.
3. Generate an index before drawing conclusions:

   ```powershell
   python skills/pix-cpp-export-toolkit/scripts/pix_cpp_export_index.py --pix-dir "<PIX C++ export path>"
   ```

4. Read the generated `pix_cpp_export_index.md` first. Use the JSON next to it for scripting.
5. Treat `Dispatch(32,32,1)`, `Dispatch(1,1,1)`, `ExecuteIndirect`, and `DrawIndexedInstanced` matches as candidates only.
6. When extracting or naming resources, follow the `resourceReader` stream from `FrameResources_000.cpp`; do not infer a `resources.bin` offset by only scanning `CreateAndInitResource_*`.
7. Record conclusions as `verified`, `candidate`, `inferred`, or `missing evidence`.

## GUI Automation Boundary

Use `scripts/pix_wpix_tool.py save-resource` only for the `pixtool save-resource` surface: event or marker based RTV export and depth visualization. Do not claim it can export arbitrary buffers, arbitrary SRV/UAV textures, or PIX GUI Resource History. For those requests, use the C++ replay and index data to build an inferred write/use chain, patch the replay for readback, or ask for a manual GUI export.

## Resources

- `scripts/pix_wpix_tool.py`: discovers `pixtool.exe`, plans or runs `.wpix` to event-list/C++ export/index workflows, and wraps RTV/depth `save-resource`.
- `scripts/pix_cpp_export_index.py`: indexes required files, reconstructs the `g_resourceReader->Read` stream, summarizes PSOs, scans command events, and writes Markdown/JSON reports.
- `references/pixtool-automation.md`: explains `.wpix` automation, CLI-supported GUI equivalents, and unsupported GUI-only surfaces.
- `references/pix-cpp-export-structure.md`: explains the core files and why read-stream order matters.
- `references/evidence-workflow.md`: generic evidence closure checklist for naming passes or resources.
- `references/domain-adapter-guide.md`: how to add project-specific semantics without polluting this generic skill.

## Boundaries

- This skill does not require any specific project, game, or renderer.
- PIX event ids, PSO ids, descriptor ids, resource ids, and root offsets can drift between captures. Re-index every new export.
- The indexer does not decompress resource payloads. It gives stable offsets, PSO anchors, and command anchors for follow-up project-specific extraction tools.
- `pixtool.exe` is an external PIX on Windows CLI, not a general PIX plugin SDK. This skill is a workflow/tool wrapper, not a PIX UI plugin.
- Use `gpu-shader-toolkit` alongside this skill when inspecting DXIL/DXBC/SPIR-V shader bytecode emitted by the export.
