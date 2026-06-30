---
name: unity-cli-skill
description: Thin gateway for the upstream akiojin/unity-cli tool. Use when installing or updating unity-cli from GitHub Releases, syncing the upstream Unity CLI workflow skills, discovering local unity-cli binaries, checking Unity bridge health, listing Unity Editor instances, calling unity-cli tool/schema/batch/system/scene commands, validating upstream Unity skills, or planning Unity Editor automation with dry-run and risk boundaries.
---

# Unity CLI Skill

## Overview

Use this skill as a small updater and command gateway for upstream `akiojin/unity-cli`. Do not copy the upstream workflow skills into this skill; sync them on demand from the release tag so they can stay current.

## Quick Workflow

1. Check the latest upstream release:

   ```powershell
   python scripts/unity_cli_tool.py release
   ```

2. Install or update the CLI binary:

   ```powershell
   python scripts/unity_cli_tool.py update-cli
   ```

   The default install target is `vendor-tools/unity-cli/bin/`. Use `UNITY_CLI_PATH` or `--install-dir` to override.

3. Verify the installed CLI:

   ```powershell
   python scripts/unity_cli_tool.py discover
   python scripts/unity_cli_tool.py version
   ```

4. Sync upstream Unity workflow skills when the user explicitly wants them:

   ```powershell
   python scripts/unity_cli_tool.py sync-skills --target targets/unity-cli/upstream-skills
   ```

5. Use command planning for Unity Editor automation:

   ```powershell
   python scripts/unity_cli_tool.py plan -- system ping
   python scripts/unity_cli_tool.py plan -- instances list
   python scripts/unity_cli_tool.py plan -- tool list
   python scripts/unity_cli_tool.py plan --dry-run -- scene create MyScene
   ```

6. Execute only low-risk health checks by default. For scene, asset, package, code, or project changes, show the planned command and risk first.

## Boundaries

- This skill owns update/discovery/planning for `unity-cli`; upstream Unity workflow skills remain upstream assets.
- Prefer `--output json` for machine-readable results.
- Prefer `--dry-run` before commands that can mutate scenes, assets, packages, project settings, or play mode state.
- Do not assume a Unity Editor is running. Check `system ping`, `instances list`, or `cli doctor` first.
- Do not run batch JSON blindly; inspect the batch payload and classify risk.

## References

- Read `references/upstream-update.md` when updating CLI binaries or syncing upstream skills.
- Read `references/command-risk.md` before executing Unity Editor automation commands.
