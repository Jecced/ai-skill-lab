---
name: environment-map-toolchain
description: Prepare and validate environment map assets for real-time rendering. Use when converting HDR or LDR panoramas, cubemaps, or cross layouts into filtered radiance cubemaps, irradiance inputs, mipmapped IBL assets, or engine-ready skybox/reflection assets; diagnosing environment-map preprocessing tools; or planning reproducible image-based lighting pipelines.
---

# Environment Map Toolchain

## Overview

Use this skill to make environment-map preprocessing repeatable and source-controlled without binding it to a specific engine. The first supported tool target is the bundled `cmft` under repository-local `vendor-tools/environment-map`, but the workflow is written around IBL asset intent: source layout, filtering, mip structure, face orientation, output format, and validation.

## Workflow

1. Inspect the source asset: HDR/LDR, equirectangular vs cubemap/cross, resolution, exposure, color space, and expected runtime.
2. Discover available tools:

   ```powershell
   python scripts/envmap_toolchain.py discover
   ```

   Set `ENVMAP_TOOLCHAIN_ROOT`, `AI_SKILL_LAB_TOOL_ROOT`, or `VENDOR_TOOLS_ROOT` only when intentionally overriding the bundled tools.

3. Decide outputs:

   - Radiance/prefiltered cubemap for specular reflections.
   - Irradiance or low-frequency diffuse lighting input.
   - Optional preview skybox or debug cube for orientation checks.

4. Generate a dry-run plan:

   ```powershell
   python scripts/envmap_toolchain.py plan --input studio.hdr --output-prefix build/studio --size 256 --mips 8
   ```

5. Execute only after confirming the local tool's help output. `cmft` flags vary across builds.
6. Validate face orientation, mip count, brightness/exposure, seams, and runtime import settings.

## References

- Read `references/cmft-workflow.md` before generating or executing `cmft` commands.
- Read `references/tool-inventory.md` when adding another environment-map processor or vendoring binaries.

## Safety

Keep source HDRs immutable. Write generated cubemaps and debug previews under a build or derived-assets folder. Do not commit large generated outputs unless they are intentional fixtures and covered by Git LFS.
