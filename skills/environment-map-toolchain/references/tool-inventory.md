# Environment Map Tool Inventory

This skill is tool-source agnostic. The repository includes a portable binary subset under `vendor-tools/environment-map`, tracked by Git LFS. Provenance is recorded in `vendor-tools/SOURCES.md`.

## Candidate Tools

| Capability | Windows paths | macOS paths |
| --- | --- | --- |
| Cubemap filtering / environment map preprocessing | `cmft\cmftRelease64.exe` | `macos/cmft/cmftRelease64` |

## Search Roots

The helper script searches in this order:

1. Repository-local `vendor-tools\environment-map`
2. `ENVMAP_TOOLCHAIN_ROOT`
3. `AI_SKILL_LAB_TOOL_ROOT`
4. `VENDOR_TOOLS_ROOT`

Set `AI_SKILL_LAB_PLATFORM=macos` or `AI_SKILL_LAB_PLATFORM=windows` to simulate platform-specific discovery from another OS.

## Vendoring Rule

Only add more tools when the workflow is repeated and the imported subset is minimal. Use Git LFS for binaries, archives, HDRs, EXRs, DDS/KTX outputs, and generated fixtures.
