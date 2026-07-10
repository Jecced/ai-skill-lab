# Captured-Effect Reconstruction Contract

## Separate Artifact Layers

Keep four layers distinct:

1. Original capture evidence: `.rdc`, raw resources, shader binaries, reflection, descriptors, hashes.
2. Readable analysis: disassembly, pass graph, constant-use notes, resource semantics.
3. Engine translation: cross-compiled shader source, loader code, format/sampler adapters.
4. Runtime integration: current camera, depth, lighting, time, transforms, and final composition.

Never overwrite layer 1 with an engine-compatible conversion.

## Resource Fidelity

For every imported resource, record original format, view format, component type, precision, dimensions, mips, slices, arrays, samples, sRGB state, raw byte count, and sampler state. If the target engine cannot sample a packed format, preserve the raw bits in a compatible integer resource and decode them in shader before considering a precision-changing conversion.

## Coordinate Ledger

Track these independently:

| Layer | Questions |
| --- | --- |
| Raw texture upload | Are row, slice, cube-face, and volume-layer orders preserved? |
| Generated intermediate RT | Does the target API use the same render-target origin? |
| Current scene depth | Which UV origin, projection convention, reversed-Z rule, and linearization are used? |
| View rays | Which handedness, basis, clip range, and corner/increment convention are expected? |
| Final display | Is this only presentation orientation, or does it feed another captured pass? |

Do not fix all layers with one global X/Y flip. Test one layer at a time and retain a reversible mapping table.

## Runtime Acceptance Gates

A visible static captured render target is only a reference. A reconstructed runtime path must pass controlled perturbations:

- Disable the effect and confirm the output changes.
- Change time and confirm a deterministic non-zero delta where animation is expected.
- Move/rotate the camera and verify view-dependent output changes coherently.
- Move/scale/rotate the effect volume and verify the rendered volume follows.
- Switch captured depth to current scene depth and verify current geometry occludes correctly.
- Change the target engine's main light only when the captured shader actually reads the mapped light constants.
- Compare intermediate outputs to locate the first divergent pass instead of masking it in the final display.

Use numeric evidence such as pixel-difference ratio, coverage, bounding box, centroid, histogram, and mask IoU when semantic image inspection is unavailable or disallowed.

## Translation Deviations

Record every unavoidable deviation with source evidence and validation status. Common examples include sampler-state mappings, derivative sampling inside dynamic loops, packed-format emulation, depth view reinterpretation, API coordinate conversion, and target-engine shader compiler constraints.

