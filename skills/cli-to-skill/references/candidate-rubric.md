# Candidate Rubric

Classify each discovered tool or folder with one of four decisions.

## Promote

Promote a candidate when all of these are true:

- It supports a repeated workflow that users actually ask agents to perform.
- It has a deterministic CLI or scriptable surface.
- A minimal subset can be copied without bringing the whole source SDK.
- Tool provenance, version, license, and redistribution status can be recorded.
- Outputs can be validated with files, hashes, sizes, logs, screenshots, or dry-run plans.
- The skill can run without the original source snapshot after vendoring or environment override.

## Defer

Defer a candidate when the idea looks useful but evidence is incomplete:

- The tool may be GUI-only or its CLI flags are unconfirmed.
- The workflow has not repeated in real use.
- The useful subset is not yet clear.
- License or redistribution status is unresolved.
- The tool depends on a large runtime that may not be portable.

Record what evidence would change the decision. Do not create a skill just to preserve a guess.

## Dependency-Only

Mark a candidate dependency-only when it is useful only underneath another workflow:

- Archive or unzip helpers.
- Runtime DLLs and shared libraries.
- Node/Python/CMake helper packages.
- Process utilities, launchers, or platform shims.

Keep these in the owning toolchain's `vendor-tools/<capability>/` subtree or installation notes. Do not make a standalone skill unless users ask for that workflow directly.

## Discard

Discard a candidate when it is stale, obsolete, too product-specific, or not safely reusable:

- Snapshot paths no longer exist or no longer represent the current toolchain.
- The tool is tightly bound to one editor installation and has no clear external workflow.
- The only available executable launches an interactive app.
- Production signing keys, private credentials, or account-specific material are mixed in.
- The candidate name describes the source product instead of a reusable capability.

## Naming Rules

- Name skills after capabilities: `texture-compression-toolchain`, not `cocos-tools`.
- Prefer `*-toolchain` when scripts discover and call multiple binaries.
- Prefer `*-audit` when the workflow is read-only and mostly judgment-based.
- Prefer `*-packaging` only when the skill can build or validate package artifacts repeatably.

## Minimum Evidence

Before promotion, capture:

```text
Source path:
Source product/version:
Tool executable or entry point:
Help/version probe:
Minimal files to copy:
Files intentionally excluded:
License/source note:
Validation command:
Expected output evidence:
```
