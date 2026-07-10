# Captured Shader Porting

## Artifact Layers

Keep these layers separate and immutable upstream:

| Layer | Required evidence |
| --- | --- |
| Original | Shader binary, encoding, stage, entry point, pipeline/event anchor, SHA-256 |
| Analysis | Disassembly, reflection, resource table, constant layout, sampler and output formats |
| Translation | Cross-compiled source plus exact tool version and command |
| Engine adapter | Includes, bindings, loader/view changes, compile target, runtime validation |

Use `scripts/shader_port_manifest.py` to record the files, hashes, commands, tools, status, and deviations.

## Constant Semantics

Do not trust decompiler names. For every constant being replaced at runtime, record:

```text
Byte offset or register:
Shader load/use:
Observed captured values:
Cross-frame variation:
Proposed semantic:
Status: verified | inferred | unresolved
Runtime replacement source:
```

A plausible direction vector is not automatically the main light. Prove that its load reaches the relevant phase, lighting, view, or output calculation. Use multiple captures that vary one input at a time when possible.

## Descriptors and Samplers

Bind shader resources using capture evidence, not just translated register names. Preserve:

- Descriptor set/space, binding number, array element, view type, byte range, and resource format.
- Sampler min/mag/mip filter, U/V/W address modes, comparison, anisotropy, LOD range/bias, and border color.
- Separate texture-object import settings from the shader sampler state.

If the target engine cannot express a captured sampler exactly, document the mapping and validate affected edge/LOD behavior. `ClampBorder -> ClampEdge` is a deviation, not an equivalent rename.

## Packed and Reinterpreted Formats

Record both resource format and view format. When direct sampling is unsupported:

1. Preserve raw bytes and texel layout.
2. Upload through a compatible integer resource when possible.
3. Decode the original packed representation in shader.
4. Compare decoded ranges or pixels against the capture.

Do not silently convert packed HDR, SNORM, depth, or typeless resources to RGBA float textures. A precision-changing conversion requires an explicit deviation and validation.

## Cross-API Control Flow

Cross-compilers and target shader compilers may reject legal source patterns from the captured API. Common adaptations include explicit loop attributes, replacing implicit-derivative sampling inside dynamic loops with explicit LOD, and rewriting unsupported sampler declarations.

For every adaptation, record:

```text
Category: control-flow | sampler | binding | format | coordinate | depth | other
Original evidence:
Translated change:
Expected semantic impact:
Validation:
```

Do not present a compiling shader as equivalent until its relevant outputs are compared.

## Coordinate Ledger

Track raw texture orientation, generated intermediate RT origin, scene-depth UV, clip/depth convention, view-ray basis, and final display orientation separately. A fix at the presentation layer must not silently change inputs to another captured pass.

## Validation Gates

- Verify source and derived artifact hashes.
- Compile the target shader and retain compiler/tool versions.
- Compare the first translated pass against the captured output before connecting later passes.
- Use range, histogram, coverage, bounding box, or pixel-delta evidence where image interpretation is unavailable.
- Perturb time, camera, transform, depth, or light only when the mapped constants are expected to respond.
- Keep status `inferred` or `unresolved` until runtime evidence closes the mapping.

