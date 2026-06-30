# Command Risk

Prefer `--output json` for every command that returns structured data.

## Low Risk

These commands are normally safe to run first:

```powershell
unity-cli --version
unity-cli cli doctor --output json
unity-cli system ping --output json
unity-cli instances list --output json
unity-cli tool list --output json
unity-cli tool schema --output json <tool-name>
unity-cli skills lint --root <path> --format json
```

They may still reveal local project paths, Unity versions, package names, and editor state.

## State-Changing

Plan and show these commands before execution:

```powershell
unity-cli scene create <name> --output json
unity-cli tool call <tool-name> --json <payload> --output json
unity-cli batch --json <payload> --output json
unity-cli instances set-active <id> --output json
unity-cli cli install --output json
```

State-changing commands can create or edit scenes, assets, components, project settings, packages, code files, or active editor targets depending on the tool payload.

## High Risk

Treat these as high risk until the exact payload is inspected:

- `tool call` that writes assets, scripts, prefabs, materials, scenes, settings, packages, or build outputs.
- `batch` payloads containing mixed read/write operations.
- Commands targeting production project directories.
- Commands that enter play mode, run tests, import packages, or regenerate code.

Before execution, report:

```text
Unity project:
Editor instance:
Command:
Payload:
Expected modified files or editor state:
Rollback/check command:
```
