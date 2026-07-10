# Upstream Selection

Primary upstream:

```text
https://github.com/JiaboLi-GitHub/renderdoc-mcp
```

Design reference:

```text
https://github.com/Linkingooo/renderdoc-mcp
```

Use the primary upstream for install, update, and configuration decisions. Use the reference upstream only to compare tool design, headless replay workflows, and output shapes.

## Package and Discovery Rules

The primary project has published packages containing some combination of:

```text
bin/renderdoc-mcp.exe
bin/renderdoc-cli.exe
bin/renderdoc.dll
renderdoc.json
skills/renderdoc-mcp/
```

Verify the requested tag and current release assets before relying on that shape. If a release exposes no archive, do not fabricate a URL; use an existing install or a source build outside the skill.

Default verified-release target:

```text
vendor-tools/renderdoc-mcp/
```

The discovery helper also checks a Codex-managed import at:

```text
${CODEX_HOME:-~/.codex}/vendor_imports/renderdoc-mcp/
```

Environment overrides:

```text
RENDERDOC_MCP_PATH=<server executable>
RENDERDOC_CLI_PATH=<CLI executable>
RENDERDOC_MCP_HOME=<upstream package directory>
RENDERDOC_RUNTIME_DIR=<directory containing the replay runtime>
QRENDERDOC_PATH=<qrenderdoc executable>
```

## Update Checklist

1. Run `renderdoc_mcp_tool.py release --tag <exact-tag>`.
2. Inspect the returned asset list and source URL.
3. Install only a verified archive with `install-release --tag <exact-tag>`.
4. Run `discover` and `doctor --capture <known-compatible.rdc>`.
5. Verify the current MCP client namespace and lightweight tool call.
6. Re-open the actual target capture. A successful `--help` probe does not prove replay compatibility.

Do not copy either upstream repository or a full RenderDoc installation into `skills/renderdoc-mcp-skill/`.
