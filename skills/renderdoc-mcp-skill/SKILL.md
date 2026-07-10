---
name: renderdoc-mcp-skill
description: Thin gateway and evidence workflow for RenderDoc MCP and local .rdc captures. Use when installing, updating, discovering, configuring, or diagnosing the JiaboLi-GitHub/renderdoc-mcp server; verifying that an MCP registration, transport, replay runtime, and concrete capture are actually compatible; exporting event-scoped pipeline, descriptor, sampler, texture, buffer, and shader evidence; building pass/resource dependency reports; or preparing an evidence-backed captured-effect reconstruction without binding the workflow to one engine or project.
---

# RenderDoc MCP Skill

Use this skill to move from "the server is installed" to a reproducible `.rdc` evidence package. Keep the MCP server name `renderdoc-mcp`; keep this workflow skill named `renderdoc-mcp-skill` so the two surfaces remain distinct.

## Route the Task

- For install, update, or upstream comparison, read `references/upstream-selection.md`.
- Before live capture, injection, or large exports, read `references/command-risk.md`.
- For service health, replay compatibility, event export, or pass graphs, read `references/capture-evidence-workflow.md`.
- Before porting a captured effect into Unity, Unreal, or another renderer, read `references/reconstruction-contract.md` and use `gpu-shader-toolkit` for shader binaries.

## Quick Workflow

1. Discover the local gateway and replay runtime:

   ```powershell
   python skills/renderdoc-mcp-skill/scripts/renderdoc_mcp_tool.py discover
   ```

2. Diagnose the four distinct layers: files, MCP configuration, transport/tool call, and concrete capture replay. The helper covers files and replay compatibility:

   ```powershell
   python skills/renderdoc-mcp-skill/scripts/renderdoc_mcp_tool.py doctor --capture "frame.rdc"
   ```

   Verify the current client's MCP namespace and a lightweight tool call separately. Do not call a registration "healthy" until the target capture opens.

3. Inspect events with MCP first. Record candidate EIDs from the current capture; never reuse EIDs or `ResourceId`s from another capture as truth.

4. Plan an exact evidence export when MCP PNG/text exports are insufficient:

   ```powershell
   python skills/renderdoc-mcp-skill/scripts/renderdoc_mcp_tool.py evidence-plan `
     --capture "frame.rdc" `
     --events 670,677,684,691 `
     --out-dir "analysis/renderdoc-exact"
   ```

5. Review the output scope, launch qrenderdoc with the planned process environment, then load and run `renderdoc_capture_export.py` from Tools > Python Shell. Require `export_status.json` to reach `complete`. Treat the generated `--python` batch candidate as version-dependent until it produces the same status and manifest on that build.

   The exporter writes raw textures, DDS files, buffers, shader bytes, disassembly, reflection, descriptors, samplers, per-event state, hashes, and `exact_export_manifest.json`.

6. Build and validate the selected-event dependency report:

   ```powershell
   python skills/renderdoc-mcp-skill/scripts/renderdoc_evidence_report.py `
     --manifest "analysis/renderdoc-exact/exact_export_manifest.json" `
     --verify-artifacts
   ```

7. Classify every conclusion as `verified`, `inferred`, or `unresolved`. Keep original capture artifacts immutable; place engine translations and compatibility edits in separate files.

## Installation and Configuration

```powershell
python skills/renderdoc-mcp-skill/scripts/renderdoc_mcp_tool.py release
python skills/renderdoc-mcp-skill/scripts/renderdoc_mcp_tool.py sources
python skills/renderdoc-mcp-skill/scripts/renderdoc_mcp_tool.py install-release
python skills/renderdoc-mcp-skill/scripts/renderdoc_mcp_tool.py mcp-config --client codex
```

Use `RENDERDOC_MCP_PATH`, `RENDERDOC_CLI_PATH`, `RENDERDOC_MCP_HOME`, or `RENDERDOC_RUNTIME_DIR` to override discovery. Verify exact upstream tags and assets before downloading.

## Boundaries

- Keep this skill thin. Do not copy upstream source trees, full RenderDoc installations, or capture-specific assets into the skill.
- Prefer existing authorized `.rdc` files before live capture or process injection.
- Do not help with stealth injection, anti-cheat bypass, protected-process evasion, or hiding RenderDoc.
- A PNG proves appearance, not original format, precision, sRGB state, mip/slice layout, or raw bytes.
- A static captured render target is a reference, not proof that a reconstructed runtime path responds to camera, time, transforms, scene depth, or lighting.
- qrenderdoc startup-script automation is build-dependent. Do not report a batch export as successful from process startup alone; require `export_status.json` and the manifest.
- Use `gpu-shader-toolkit` for DXBC, DXIL, and SPIR-V analysis and cross-compilation. This skill owns capture context and resource evidence.
