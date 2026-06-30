# Vendor Records

Use this reference when a candidate moves from local snapshot to repository-owned `vendor-tools/`.

## Source Record

Add or update `vendor-tools/SOURCES.md` with one entry per imported tool family:

```markdown
## <capability>/<tool-name>

- Source: <URL or local source snapshot>
- Source product/version: <SDK/editor/tool version>
- Retrieved: <YYYY-MM-DD>
- Imported files:
  - `vendor-tools/<capability>/<path>`
- Excluded files:
  - <large folders, docs, samples, private keys, caches>
- License/redistribution: <known status or unresolved>
- Validation:
  - `<command used to print version/help>`
  - `<command used by the owning skill discovery script>`
```

If license status is unresolved, keep the record explicit and avoid broad redistribution claims.

## Git LFS Coverage

Before adding binary or archive files, check `.gitattributes` for patterns covering:

```text
*.exe
*.dll
*.dylib
*.so
*.zip
*.7z
*.tar
*.gz
*.png
*.jpg
*.tga
*.dds
*.ktx
*.astc
```

Run these checks before commit:

```powershell
git lfs status
git diff --check
```

## Tool Discovery Expectations

Every promoted toolchain skill should be able to discover tools from at least one of:

- Repository-local `vendor-tools/<capability>/`.
- A capability-specific environment variable such as `TEXTURE_TOOLCHAIN_ROOT`.
- A shared override such as `AI_SKILL_LAB_TOOL_ROOT` or `VENDOR_TOOLS_ROOT`.

Prefer repository-local paths first so another machine can run after `git lfs pull`.

## Validation Evidence

For each imported tool family, keep a small validation trail:

```text
Tool path:
Version/help output:
Dry-run command:
Executed command, if any:
Output files:
Known platform limits:
```

Do not treat a copied file as a working toolchain until discovery and at least one low-risk command have been run from the vendored path.
