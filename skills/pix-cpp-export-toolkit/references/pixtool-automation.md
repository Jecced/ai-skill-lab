# pixtool Automation Boundary

Use this reference when starting from a `.wpix` capture path or when a user asks whether a PIX GUI action can be automated.

## Supported CLI Path

PIX on Windows installs `pixtool.exe` with a public command surface that can open captures and save selected outputs. Use the wrapper script to keep commands reproducible:

```powershell
python skills/pix-cpp-export-toolkit/scripts/pix_wpix_tool.py discover
python skills/pix-cpp-export-toolkit/scripts/pix_wpix_tool.py prepare --capture frame.wpix --execute
```

The `prepare` command writes a capture-scoped analysis folder containing:

- `event-list.csv` from `pixtool open-capture ... save-event-list`
- `cpp-export/` from `pixtool open-capture ... export-to-cpp`
- `indexes/cpp-export/pix_cpp_export_index.md`
- `indexes/cpp-export/pix_cpp_export_index.json`

Without `--execute`, every command is a dry-run plan. Use this before running long exports or when the capture path is only a placeholder.

## GUI Feature Mapping

| User request | CLI path | Status |
| --- | --- | --- |
| Convert `.wpix` to C++ replay | `prepare` or `export-cpp` | Supported |
| Save event list with counters | `prepare` or `event-list` | Supported |
| Save a draw event RTV | `save-resource --global-id <id> --rtv <n>` | Supported |
| Save depth visualization | `save-resource --global-id <id> --depth --output out.png` | Supported, PNG only |
| Export arbitrary buffer by resource id/name | No public `pixtool` flag | Not supported directly |
| Export arbitrary SRV/UAV texture by resource id/name | No public `pixtool` flag | Not supported directly |
| Show or export Resource History | No public `pixtool` command | Not supported directly |
| Add a custom PIX UI panel/menu/plugin | No public plugin SDK | Not supported directly |

When a request falls outside the CLI path, do not pretend `pixtool` can do it. Use one of these fallbacks:

1. Patch the exported C++ replay to add a readback and dump path for the target resource.
2. Parse `FrameResources_000.cpp`, `CapturedAssets.h`, descriptors, and `resources.bin` with a project-specific extractor.
3. Ask for a one-time PIX GUI export when the requested view has no CLI equivalent.

## Resource History Substitute

The skill can reconstruct a code-level history, but it is not the PIX GUI Resource History view. Build the substitute history from:

1. Resource creation metadata in `CapturedAssets.h`.
2. Compressed payload offsets from the `resourceReader` stream in `FrameResources_000.cpp`.
3. Descriptor use in `Descriptors_*.cpp` if present.
4. Barriers, copies, clears, UAV writes, render target binds, dispatches, and draws in `CommandLists_*.cpp`.
5. PSO and shader evidence from `CreatePSOs.cpp` and shader bytecode tools.

Report this as an inferred write/use chain unless resource contents or replay readback confirms the actual data.

## Command Examples

Create a full analysis folder:

```powershell
python skills/pix-cpp-export-toolkit/scripts/pix_wpix_tool.py prepare `
  --capture "D:\captures\frame.wpix" `
  --output-root ".pix-analysis\pix-captures" `
  --label frame_001 `
  --force `
  --execute
```

Export only C++ replay:

```powershell
python skills/pix-cpp-export-toolkit/scripts/pix_wpix_tool.py export-cpp `
  --capture "D:\captures\frame.wpix" `
  --output-dir ".pix-analysis\pix-captures\frame_001\cpp-export" `
  --force `
  --execute
```

Save an event list with counters:

```powershell
python skills/pix-cpp-export-toolkit/scripts/pix_wpix_tool.py event-list `
  --capture "D:\captures\frame.wpix" `
  --output ".pix-analysis\pix-captures\frame_001\event-list.csv" `
  --counters "*" `
  --execute
```

Save an RTV or depth image:

```powershell
python skills/pix-cpp-export-toolkit/scripts/pix_wpix_tool.py save-resource `
  --capture "D:\captures\frame.wpix" `
  --output ".pix-analysis\pix-captures\frame_001\rtv0.png" `
  --global-id 1234 `
  --rtv 0 `
  --execute

python skills/pix-cpp-export-toolkit/scripts/pix_wpix_tool.py save-resource `
  --capture "D:\captures\frame.wpix" `
  --output ".pix-analysis\pix-captures\frame_001\depth.png" `
  --global-id 1234 `
  --depth `
  --execute
```
