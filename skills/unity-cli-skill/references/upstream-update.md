# Upstream Update

Upstream project:

```text
https://github.com/akiojin/unity-cli
```

Release API:

```text
https://api.github.com/repos/akiojin/unity-cli/releases/latest
```

Current verified release at the time this skill was created:

```text
tag: v0.12.0
published_at: 2026-06-23T16:26:36Z
license: MIT
```

Use `scripts/unity_cli_tool.py release` for current data before updating.

## CLI Binary

The release publishes platform-specific assets and `unity-cli-manifest.json`.

Expected platform keys:

- `win-x64`
- `linux-x64`
- `linux-arm64`
- `osx-arm64`

The updater downloads the matching asset, verifies SHA256 from `unity-cli-manifest.json`, writes `unity-cli.exe` on Windows or `unity-cli` elsewhere, and records `VERSION.json` next to the binary.

Default install path:

```text
vendor-tools/unity-cli/bin/
```

## Upstream Skills

The Codex plugin metadata points to the shared upstream skill source:

```text
.claude-plugin/plugins/unity-cli/skills/
```

Use the release tag source archive to sync these skills. Do not copy `.agents/skills/unity-*` pointer files; they are not the actual skill bodies.

Default local sync target:

```text
targets/unity-cli/upstream-skills/
```

Keep synced upstream skills separate from this repository's hand-authored `skills/` so local changes and upstream updates do not get mixed.

## Update Checklist

1. Run `python scripts/unity_cli_tool.py release`.
2. Run `python scripts/unity_cli_tool.py update-cli`.
3. Run `python scripts/unity_cli_tool.py version`.
4. Optionally run `python scripts/unity_cli_tool.py sync-skills --target targets/unity-cli/upstream-skills`.
5. Run `unity-cli cli doctor --output json` through `plan` or directly only when a Unity project/editor context is intended.
