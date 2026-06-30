# Domain Adapter Guide

Keep this skill generic. Add project-specific meaning through a thin adapter layer when a capture belongs to a known engine, game, or internal renderer.

## What Belongs In The Generic Skill

- PIX C++ export file structure.
- PSO, command list, resourceReader, and resource metadata indexing.
- Evidence status language.
- Generic candidates such as dispatch, draw, and indirect execution patterns.
- Commands that can run on any export with the required files.

## What Belongs In A Domain Adapter

- Game, project, or engine names.
- Known pass names.
- Known resource semantics.
- Capture-specific event ids, PSO ids, descriptor ids, root constant offsets, or buffer row layouts.
- Extraction scripts for domain-specific buffers or textures.

## Adapter Shape

A project adapter can be another skill or a folder next to the analysis output. Keep it small:

```text
project-pix-adapter/
  SKILL.md
  references/
    known-pass-patterns.md
    resource-layouts.md
  scripts/
    extract_project_resources.py
```

The adapter should call the generic indexer first, then layer its own naming rules on top of the generated JSON. This keeps the reusable PIX workflow stable while allowing each project to carry its own evidence vocabulary.
