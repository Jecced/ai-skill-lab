---
name: texture-compression-toolchain
description: Plan, execute, and validate texture compression and image conversion workflows for game and rendering assets. Use when converting or batch-processing textures such as PNG, TGA, BMP, DDS, KTX, ASTC, ETC, PVRTC, or WebP; choosing mobile or web texture formats; reducing asset size; preserving alpha, normal maps, or color space; comparing compressed outputs; or diagnosing local texture tool availability.
---

# Texture Compression Toolchain

## Overview

Use this skill to turn a user request like "compress these textures for Android" into a concrete, validated toolchain plan. Keep the skill independent from any one engine or editor. The default tools are bundled under repository-local `vendor-tools/texture-compression`; environment variables are only for overriding or testing another toolchain.

## Workflow

1. Inspect inputs before choosing a format: source extension, dimensions, alpha, normal-map status, HDR/LDR, sRGB/linear color space, and target runtime.
2. Discover available tools:

   ```powershell
   python scripts/texture_toolchain.py discover
   ```

   Set `TEXTURE_TOOLCHAIN_ROOT`, `AI_SKILL_LAB_TOOL_ROOT`, or `VENDOR_TOOLS_ROOT` only when intentionally overriding the bundled tools.

3. Select a target family using `references/texture-format-guide.md`.
4. Generate a dry-run command plan before touching assets:

   ```powershell
   python scripts/texture_toolchain.py plan --input in.png --output out.webp --format webp --quality high
   ```

5. Execute with explicit output paths. Do not overwrite source textures unless the user asks for an in-place rewrite.
6. Validate the output: file exists, size changed as expected, dimensions are preserved unless resizing was requested, alpha is preserved when required, and important assets get visual review.

## Format Selection

- Use ASTC for modern mobile GPUs when quality and broad Android/iOS support matter.
- Use ETC/ETC2 when ASTC is unavailable or when targeting older Android/OpenGL ES paths.
- Use PVRTC only for legacy iOS or constrained pipelines that explicitly require it.
- Use WebP for web delivery, UI textures, preview assets, or source-size reduction where the runtime can decode it.
- Keep normal maps and masks out of lossy color-compression defaults unless the target format and swizzle are deliberate.

Read `references/texture-format-guide.md` for the detailed matrix.

## Tool Notes

Read `references/tool-inventory.md` when tool discovery fails, when adding a new binary source, or when deciding what belongs in Git LFS. Keep binaries in `vendor-tools/`, not inside the skill folder.

The helper script is intentionally dry-run oriented. It can produce command candidates, but the agent must still check tool-specific help before using uncommon formats or flags.
