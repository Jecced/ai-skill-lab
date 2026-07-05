# Evidence Workflow

Use this checklist when turning a PIX C++ export into a named render pass, resource, or data structure.

## Stable First Pass

1. If starting from `.wpix`, run `scripts/pix_wpix_tool.py prepare` to produce the event list, C++ export, and index. If starting from an existing export, run the indexer directly.
2. Keep both Markdown and JSON index outputs.
3. Record the capture/export path, label, tool command, `pixtool.exe` path when used, and generated report path.
4. Identify candidate events from command shape only:
   - `Dispatch(x,y,z)`
   - `ExecuteIndirect`
   - `DrawIndexedInstanced`
   - barriers and transitions around the candidate event
5. Record the command list file, line, command list object id, nearby comments, current PSO, and current root parameters.

## Event Id Mapping

PIX GUI labels and replay C++ ids are easy to mix up. Keep all available anchors together:

- GUI `Global ID` maps most directly to comments in `CommandLists_*.cpp`, such as `GlobalId = <n>`.
- GUI `Queue ID` or `Command ID` is a PIX UI event coordinate. It is useful evidence, but it usually is not written directly as a replay C++ id.
- C++ `GetCommandList(<id>)` is a D3D12 command list object id. Do not present it as a GUI Global ID.

When the GUI Global ID is available, search it in `CommandLists_*.cpp` and record the line plus the following API call. When only Queue ID or Command ID is available, match by API name, adjacent events, current PSO, root constants, argument buffers, resource ids, and nearby barriers, then record the closest C++ file and line.

## Closure Table

| Link | Required evidence | Common source | Status wording |
| --- | --- | --- | --- |
| Command shape | Dispatch/draw/indirect pattern and surrounding barriers | `CommandLists_*.cpp`, index report | Candidate |
| PSO binding | PSO id, graphics/compute type, root signature, shader stages, shader byte sizes | `CreatePSOs.cpp`, index report | Verified or candidate |
| Root parameters | Constants, descriptor tables, offsets, argument buffers | `CommandLists_*.cpp` | Verified, candidate, or unknown |
| Descriptor/resource | SRV/UAV/CBV resource id, format, dimensions, subresources | `Descriptors_*.cpp`, `CapturedAssets.h` | Verified or candidate |
| Shader access | DXIL/DXBC access pattern, buffer stride, texture sampling, UAV writes | Shader dump plus `gpu-shader-toolkit` | Verified or inferred |
| Data sample | Fixed sample rows, pixels, counters, or payload chunks | Follow-up extraction script | Verified |
| Domain name | Final pass/resource meaning | All previous links | Verified or missing evidence |

## Rules

- Do not reuse ids from an old capture as truth for a new capture.
- Do not name a pass from dispatch dimensions alone.
- Keep uncertainty explicit. `candidate` is better than a precise but unsupported name.
- When visual output looks wrong, revisit the producing pass and resource evidence before changing the consuming runtime.
- `pixtool save-resource` covers event/marker RTV and depth exports. Treat arbitrary buffer/texture exports and Resource History as GUI-only or replay-patch work unless another verified tool is available.
- `pix_stream_extract.py` extracts frame-start replay payloads and PSO shader bytecode. It does not prove the later contents of resources that are written during the frame.
