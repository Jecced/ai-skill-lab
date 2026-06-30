# Texture Format Guide

Use this file when the user has not already specified a target format.

## Decision Matrix

| Target | Prefer | Use when |
| --- | --- | --- |
| Modern mobile | ASTC | Android/iOS GPU support is expected and quality per bit matters. |
| Older Android/OpenGL ES | ETC2 or ETC1 | ASTC support cannot be assumed. ETC1 needs special handling for alpha. |
| Legacy iOS | PVRTC | The runtime or asset pipeline explicitly requires PVRTC. |
| Web delivery or previews | WebP | The runtime can decode WebP or the asset is for distribution/preview, not GPU-native upload. |
| Desktop authoring interchange | PNG, TGA, DDS, KTX | Preserve source quality or maintain engine import compatibility. |

## Asset-Type Rules

- Color/albedo: track sRGB intent; lossy compression is usually acceptable after visual review.
- Normal maps: avoid color-oriented lossy settings unless the format and encoder are known to preserve vectors acceptably.
- Masks: validate each channel after compression; artifacts can change roughness, metallic, AO, or opacity behavior.
- UI textures: prefer sharper quality settings and compare text/edge artifacts.
- HDR environment inputs: keep in the environment-map workflow; do not route HDR lighting maps through WebP/ASTC defaults.

## Command Families

These are starting points, not a substitute for local `--help` output:

- WebP encode: `cwebp -q 85 input.png -o output.webp`
- WebP decode: `dwebp input.webp -o output.png`
- ASTC LDR encode: `astcenc -cl input.png output.astc 6x6 -medium`
- PVRTC/PVR family: use `PVRTexToolCLI`; confirm exact `-f` format strings with local help.
- ETC family: use `etcpack` or a PVRTexTool ETC format; confirm exact flags with local help.

Always write to an explicit output path and keep source textures immutable by default.
