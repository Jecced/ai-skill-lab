---
name: cli-to-skill
description: Inspect local CLI, SDK, editor, engine, or tool snapshot directories and decide whether any subset should become a reusable AI skill. Use when auditing command-line tools or third-party tool folders, promoting tools into vendor-tools, designing a new skill from discovered binaries, recording source/version/license evidence, creating Git LFS coverage for vendored binaries, or removing stale snapshot-based candidates.
---

# CLI To Skill

## Overview

Use this skill to turn an arbitrary local CLI or tool snapshot into a small, reusable, evidence-backed skill. The goal is not to wrap a whole SDK; it is to identify the minimum portable subset that supports a repeated workflow and can be validated on another machine.

## Workflow

1. Define the target workflow before scanning deeply. Write the user-facing job in one sentence, such as "batch-compress mobile textures" or "prepare IBL cubemaps."
2. Inspect the source snapshot read-only:

   ```powershell
   python scripts/toolchain_snapshot.py scan --root "<tool snapshot path>" --markdown
   ```

3. Read `references/candidate-rubric.md` and classify each candidate as `promote`, `defer`, `dependency-only`, or `discard`.
4. Prove the CLI surface before copying binaries. For trusted local tools only, run bounded help/version probes:

   ```powershell
   python scripts/toolchain_snapshot.py probe --tool "<path to exe or script>" --mode help
   python scripts/toolchain_snapshot.py probe --tool "<path to exe or script>" --mode version
   ```

5. Design the skill boundary around a reusable workflow, not the source product. Name the skill after the capability, not the folder it came from.
6. Copy only the smallest useful subset into `vendor-tools/<capability>/` after license/source risk is acceptable.
7. Record provenance using `references/vendor-records.md`. Update `vendor-tools/SOURCES.md`, `.gitattributes`, and any tool discovery script together.
8. Validate portability: run discovery from the vendored path, generate a dry-run plan, and confirm the skill does not depend on the original source snapshot.
9. Delete stale snapshot reports once their useful conclusions have been promoted into skills, references, scripts, or vendor source records.

## Decision Rules

- Promote when the workflow is repeated, the tool has a non-interactive CLI, the useful subset is small, provenance is clear, and outputs can be validated.
- Defer when the command surface is unknown, the workflow has not repeated, the tool is mostly GUI-only, or copying would bring a large dependency tree.
- Treat runtime helpers as dependency-only when they merely support another promoted workflow.
- Discard stale snapshot conclusions when the source path no longer reflects current reality.

## Resources

- `scripts/toolchain_snapshot.py`: read-only scanner, bounded CLI probe, and promotion manifest template generator.
- `references/candidate-rubric.md`: classification rules and red flags for toolchain candidates.
- `references/vendor-records.md`: source-record, LFS, and validation evidence checklist.

## Reporting

End with a concise promotion decision:

```text
Decision: promote | defer | dependency-only | discard
Capability name:
Source snapshot:
Minimal subset:
Required skill resources:
Validation commands:
License/source gaps:
Do not copy:
```
