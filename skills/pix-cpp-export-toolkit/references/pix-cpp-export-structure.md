# PIX C++ Export Structure

PIX on Windows can export a capture as a replayable C++ project. The files are useful even when the replay project is not compiled, because they preserve the command stream, PSO definitions, resource initialization metadata, and compressed resource payload stream.

## Required Files

| File | Use |
| --- | --- |
| `FrameResources_000.cpp` | High-level replay initialization order. Use it to reconstruct the `resources.bin` read stream. |
| `CreatePSOs.cpp` | Graphics/compute PSO definitions, root signatures, shader bytecode reads, input layouts, and render target/depth formats. |
| `CommandLists_*.cpp` | Command order, `SetPipelineState`, root constants, descriptor setup, barriers, dispatches, draws, and indirect execution. |
| `CapturedAssets.h` | Resource initialization metadata such as format, dimensions, row pitch, subresources, and resource init ids. |
| `resources.bin` | Compressed payload stream used by the C++ replay. It can include resource data and PSO shader bytecode blocks. |

## Read-Stream Rule

`resources.bin` is not a direct `resource id -> file offset` table. Reconstruct offsets by walking the replay read order:

1. Scan all C++ functions for `g_resourceReader->Read(data, size)` calls.
2. Read the no-argument function call order in `FrameResources_000.cpp`.
3. Accumulate every read size in order, including `CreateGraphicsPipelineState_*` and `CreateComputePipelineState_*`.
4. Only when the current function is `CreateAndInitResource_<id>` should the current compressed offset be recorded as that resource block.

If shader bytecode reads are skipped, later resource offsets can shift and any extracted payload can be wrong even when the resource id looks plausible.
