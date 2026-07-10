# Command Risk

Prefer an existing authorized `.rdc` for first analysis. Live capture has more moving parts and can affect target processes.

## Low Risk

Normally safe to run first:

```powershell
renderdoc-cli.exe --help
renderdoc-cli.exe version
renderdoc-cli.exe <capture.rdc> info
```

Read-only MCP operations over an opened local capture are also normally low risk: metadata, event lists, pipeline state, bindings, shader metadata, resource lists, pixel statistics, and assertions that do not write files.

## Review Before Running

Show the output scope before exporting raw evidence:

```text
Capture path:
Tool executable:
Events:
Output directory:
Expected generated files:
Privacy or IP risk:
Cleanup path:
```

Raw textures, buffers, and shaders can be large or proprietary. Default to an explicit analysis directory outside the skill repository.

## High Risk

Treat these as high risk:

- Launching or attaching to a process for capture.
- Remote capture or process injection.
- Capturing protected, competitive, anti-cheat, or third-party production software without clear authorization.
- Hiding RenderDoc, bypassing detection, or altering injection behavior for stealth.

For legitimate local-development capture, require a clearly scoped target and bounded output directory.
