# Environment Map Tool Inventory

This skill is tool-source agnostic. The repository includes a portable binary subset under `vendor-tools/environment-map`, tracked by Git LFS. Provenance is recorded in `vendor-tools/SOURCES.md`.

## Candidate Tools

| Capability | Candidate executable | Common source-relative paths |
| --- | --- | --- |
| Cubemap filtering / environment map preprocessing | `cmftRelease64.exe` | `cmft\cmftRelease64.exe` |

## Search Roots

The helper script searches in this order:

1. Repository-local `vendor-tools\environment-map`
2. `ENVMAP_TOOLCHAIN_ROOT`
3. `AI_SKILL_LAB_TOOL_ROOT`
4. `VENDOR_TOOLS_ROOT`

## Vendoring Rule

Only add more tools when the workflow is repeated and the imported subset is minimal. Use Git LFS for binaries, archives, HDRs, EXRs, DDS/KTX outputs, and generated fixtures.
