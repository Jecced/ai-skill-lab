# CMFT Workflow Notes

Use this file when planning commands for `cmftRelease64.exe`.

## Inputs

Confirm these before generating commands:

- Source layout: equirectangular panorama, horizontal/vertical cross, face list, or existing cubemap.
- Dynamic range: HDR sources should stay HDR through preprocessing unless the user explicitly wants LDR.
- Face orientation: prepare a debug preview cube if the target engine has known face-order differences.
- Resolution: choose a power-of-two face size appropriate for runtime memory.
- Mip count: specular radiance maps usually need multiple mips; diffuse/irradiance maps usually need a smaller filtered output.

## Outputs

Common derived assets:

- Radiance or prefiltered specular cubemap with mip chain.
- Irradiance or low-frequency diffuse lighting cubemap.
- Preview skybox or face strip for orientation checks.

## Command Planning

`cmft` builds can differ. Always run local help before executing generated command candidates:

```powershell
cmftRelease64.exe --help
```

Treat helper-script output as a starting point. Confirm exact names for:

- `--input`
- `--filter`
- `--srcFaceSize`
- `--dstFaceSize`
- `--mipCount`
- `--output0`
- `--output0params`

## Validation

- Load the output in a viewer or engine import path and check all six faces.
- Verify the brightest light direction is still correct after conversion.
- Check mip chain count and roughness progression for radiance maps.
- Look for seams at cube edges.
- Record source file, tool path, tool version/help text, face size, mip count, and output params.
