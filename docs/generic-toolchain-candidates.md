# Generic Toolchain Candidates

Source snapshot inspected: `C:\ProgramData\cocos\editors\Creator\3.8.8\resources\tools`

Inspection date: 2026-06-30

## Summary

This folder is useful as a source snapshot of general-purpose toolchains. Do not let the source product name define the skill names. Skill names should describe reusable capabilities, not where the binaries were found.

The first portable subset has been copied into `vendor-tools/` so the promoted skills can run on another machine without the original source path.

Observed size:

| Item | Value |
| --- | ---: |
| Total files | 16,510 |
| Total size | 267.21 MB |
| Largest directory | `cmake`, 94.99 MB |
| Largest file | `quickgame-toolkit.zip`, 31.92 MB |

Largest top-level entries:

| Entry | Files | Size |
| --- | ---: | ---: |
| `cmake` | 6,949 | 94.99 MB |
| `Python27-win32` | 3,096 | 47.35 MB |
| `quickgame-toolkit.zip` | 1 | 31.92 MB |
| `mali_win32` | 9 | 30.87 MB |
| `lightmap-tools` | 1 | 18.10 MB |
| `huawei-rpk-tools` | 6,323 | 15.56 MB |
| `openSSLWin64` | 59 | 9.32 MB |
| `libwebp_win32` | 25 | 7.93 MB |
| `PVRTexTool_win32` | 2 | 6.41 MB |

Largest file types by size:

| Extension | Files | Size |
| --- | ---: | ---: |
| `.exe` | 36 | 112.32 MB |
| `.zip` | 2 | 31.92 MB |
| `.html` | 1,900 | 21.54 MB |
| `.dll` | 24 | 21.22 MB |
| `.py` | 1,419 | 16.95 MB |
| `.js` | 4,812 | 12.23 MB |
| `.qch` | 1 | 6.30 MB |
| `.chm` | 1 | 5.72 MB |

## Skill Candidates

### 1. `texture-compression-toolchain`

Recommendation: promoted to `skills/texture-compression-toolchain`.

Bundled subset: `vendor-tools/texture-compression`.

Candidate tools:

- `astc-encoder\astcenc.exe`
- `mali_win32\astcenc.exe`
- `mali_win32\etcpack.exe`
- `mali_win32\convert.exe`
- `mali_win32\composite.exe`
- `PVRTexTool_win32\PVRTexToolCLI.exe`
- `PVRTexTool_win32\compare.exe`
- `libwebp_win32\bin\cwebp.exe`
- `libwebp_win32\bin\dwebp.exe`

Skill shape:

- `SKILL.md`: decide target texture format by platform, quality, alpha use, color space, and runtime constraints.
- `references/`: keep command examples, input/output matrix, compression tradeoffs, and validation rules.
- `scripts/`: provide wrappers for batch conversion, dry-run plans, output validation, and before/after size reports.
- `vendor-tools/`: keep binaries only after license and redistribution review.

This is the strongest candidate because texture conversion is repetitive, parameter-sensitive, and easy to validate from output files.

### 2. `quickgame-packaging`

Recommendation: high value if quick-game publishing is a repeated workflow.

Candidate tools:

- `quickgame-toolkit.zip`
- `huawei-rpk-tools`
- `honor-pack-tools`
- `xiaomi-pack-tools`
- `keystore\debug.keystore`

Observed package metadata:

- `huawei-rpk-tools` package name is `fa-sign-tools`, described as signing a build directory and generating an `rpk` file.
- `honor-pack-tools` depends on `@honor-minigame/cli` and exposes pack/release/version scripts.
- `xiaomi-pack-tools` depends on `quickgame-cli` and exposes build, release, server, and debug scripts.

Skill shape:

- `SKILL.md`: guide platform selection, debug vs release build, signing inputs, and validation checklist.
- `references/`: document Huawei/Honor/Xiaomi command differences and error patterns.
- `scripts/`: wrap per-platform packaging with explicit input paths and non-interactive output.

Do not commit real release signing keys. The bundled `debug.keystore` can be treated as disposable test material, but production keys should stay outside the repo.

### 3. `lightmap-uv-toolchain`

Recommendation: medium value, defer until a real lightmap or UV workflow repeats.

Candidate tools:

- `lightmap-tools\LightFX.exe`
- `LightFX\uvunwrap.exe`

Notes:

- `LightFX.exe` appears to start as an application process when probed.
- The CLI surface was not confirmed in this pass.

Skill shape:

- Start as a reference-only troubleshooting skill for lightmap bake inputs, UV unwrap constraints, outputs, and validation.
- Add scripts only after the command surface is proven non-interactive.

### 4. `environment-map-toolchain`

Recommendation: promoted to `skills/environment-map-toolchain`.

Bundled subset: `vendor-tools/environment-map`.

Candidate tools:

- `cmft\cmftRelease64.exe`

Skill shape:

- Use for cubemap filtering, environment map preprocessing, and reproducible IBL asset generation.
- Keep separate from texture compression if the workflow becomes rendering/lighting specific.

### 5. `native-build-diagnostics`

Recommendation: low as a standalone skill, useful as a reference dependency set.

Candidate tools:

- `cmake`
- `Python27-win32`
- `openSSLWin64`

This should focus on diagnosing old native build environments and dependency resolution. It should not become a generic CMake tutorial.

### 6. Tool Dependencies, Not Skill Roots

Recommendation: do not make standalone skills now.

Items:

- `windows-process-tree`: Node native dependency for Windows process tree lookup.
- `native-scene`: native Node addon and `SDL2.dll`.
- `unzip.exe`: generic unpack helper.

Keep these as implementation dependencies only if a higher-level skill needs them.

## Import Policy

Do not copy the full source snapshot into this repo until all of these are true:

1. The intended skill workflow is clear and repeated.
2. Redistribution and license constraints are acceptable.
3. The imported subset is minimal.
4. Every imported binary is covered by Git LFS.
5. A version/source note is kept beside the imported subset.

Preferred future layout:

```text
skills/
  texture-compression-toolchain/
  quickgame-packaging/
  environment-map-toolchain/
targets/
  codex/
  claude/
  trae/
vendor-tools/
  texture-compression/
  quickgame-packaging/
  environment-map/
docs/
  generic-toolchain-candidates.md
```

## Next Step

Start with `texture-compression-toolchain`. It has the best balance of repeatability, deterministic validation, and usefulness across AI agents. Keep the first version binary-optional: prefer detecting a configured local tools path and only fall back to vendored binaries if needed.
