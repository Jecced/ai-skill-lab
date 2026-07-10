# Capture Evidence Workflow

## Health Matrix

Treat these as separate states:

| Layer | Evidence | Meaning |
| --- | --- | --- |
| Files | Server, CLI, runtime, configuration exist | Installation is present |
| Client exposure | MCP namespace is visible | Current client discovered the server |
| Transport | Lightweight MCP call returns | Handshake and request path work |
| Replay | The concrete `.rdc` opens without degradation | Runtime is compatible with this capture |

Do not collapse them into one "service healthy" result. A runtime can answer MCP requests yet reject a newer Vulkan or D3D capture.

## Event Selection

1. Open the capture and record API, RenderDoc version, event count, and degradation state.
2. Locate candidate events from the current capture using pass structure, render-target formats, resource usage, shader access, and output statistics.
3. Export a small chain first: producer, suspected effect pass, and first consumer that materially changes the output.
4. Re-resolve event and resource IDs for every capture. IDs can drift even when content is visually similar.

## Exact Export Contract

For every selected event, preserve:

- Graphics/compute pipeline object and shader stage/entry point.
- Color/depth output descriptors and raw resources.
- Read-only/read-write resources and descriptor view format.
- Constant-buffer byte offset, byte size, raw bytes, and reflection layout.
- Sampler filter, addressing, LOD, comparison, and border state.
- Original shader bytes, encoding, disassembly, and reflection.
- Texture format, dimensions, depth, mips, array size, sample count, sRGB state, byte size, DDS, and raw subresource data.
- SHA-256 and export errors.

Use `renderdoc_capture_export.py` inside qrenderdoc's Python Shell. `evidence-plan` supplies capture, output, and EIDs through process-scoped `RENDERDOC_EXPORT_*` variables because qrenderdoc does not forward arbitrary script arguments. Require `export_status.json` to report `complete`; opening a qrenderdoc process is not export evidence. The optional `--python` startup form is build-dependent and must be revalidated. Then run `renderdoc_evidence_report.py` to reconstruct producer/consumer links between selected events and verify artifacts.

## Trace the First Meaningful Change

When the visible result differs from an intermediate render target, do not immediately tune lighting, exposure, or display code. Follow resource usage forward and compare output statistics until the first pass that changes the relevant signal. Record that pass and its full inputs before porting it.

## Status Vocabulary

- `verified`: directly supported by capture state, shader access, raw resource data, or controlled runtime output.
- `inferred`: best explanation consistent with multiple evidence sources, but not directly named or decoded.
- `unresolved`: required evidence is missing, exporter failed, or engine translation has not been validated.
