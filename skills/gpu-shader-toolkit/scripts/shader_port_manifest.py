#!/usr/bin/env python3
"""Create and verify provenance manifests for captured shader ports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ARTIFACT_FLAGS = {
    "disassembly": "disassembly",
    "reflection": "reflection",
    "translated": "translated-source",
    "adapter": "engine-adapter",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path, root: Path, kind: str) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise SystemExit(f"artifact not found: {resolved}")
    try:
        stored_path = os.path.relpath(resolved, root).replace("\\", "/")
    except ValueError:
        stored_path = str(resolved)
    return {
        "kind": kind,
        "path": stored_path,
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def parse_pairs(values: list[str], option: str) -> list[dict[str, str]]:
    result = []
    for value in values:
        if "=" not in value:
            raise SystemExit(f"{option} must use key=value: {value}")
        key, text = value.split("=", 1)
        if not key.strip() or not text.strip():
            raise SystemExit(f"{option} must use non-empty key=value: {value}")
        result.append({"name" if option == "--tool" else "category": key.strip(), "value" if option == "--tool" else "description": text.strip()})
    return result


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def create_manifest(args: argparse.Namespace) -> int:
    output = Path(args.output).expanduser().resolve()
    root = output.parent
    source = artifact(Path(args.source), root, "original-binary")
    source.update({"encoding": args.encoding, "stage": args.stage, "entryPoint": args.entry})
    derived = []
    for argument, kind in ARTIFACT_FLAGS.items():
        value = getattr(args, argument)
        if value:
            derived.append(artifact(Path(value), root, kind))
    tools = parse_pairs(args.tool, "--tool")
    deviations = parse_pairs(args.deviation, "--deviation")
    manifest = {
        "schema": 1,
        "status": args.status,
        "source": source,
        "artifacts": derived,
        "tools": [{"name": item["name"], "versionOrSource": item["value"]} for item in tools],
        "commands": args.command,
        "translationDeviations": deviations,
        "evidence": {
            "pipelineOrEvent": args.anchor,
            "notes": args.note,
        },
    }
    write_json(output, manifest)
    print(json.dumps({"manifest": str(output), "artifacts": 1 + len(derived)}, indent=2))
    return 0


def iter_artifacts(manifest: dict[str, Any]):
    yield manifest["source"]
    yield from manifest.get("artifacts", [])


def verify_manifest(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).expanduser().resolve()
    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    results = []
    for item in iter_artifacts(manifest):
        stored_path = Path(item["path"])
        path = stored_path.resolve() if stored_path.is_absolute() else (manifest_path.parent / stored_path).resolve()
        if not path.is_file():
            results.append({"kind": item.get("kind"), "path": str(path), "status": "missing"})
            continue
        actual = sha256_file(path)
        expected = item.get("sha256")
        results.append(
            {
                "kind": item.get("kind"),
                "path": str(path),
                "status": "pass" if actual == expected else "hash-mismatch",
                "expectedSha256": expected,
                "actualSha256": actual,
            }
        )
    print(json.dumps({"manifest": str(manifest_path), "results": results}, indent=2))
    return 0 if all(item["status"] == "pass" for item in results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command_name", required=True)

    create = sub.add_parser("create", help="Create a captured shader port manifest")
    create.add_argument("--source", required=True)
    create.add_argument("--encoding", required=True)
    create.add_argument("--stage", required=True)
    create.add_argument("--entry", default="main")
    create.add_argument("--disassembly")
    create.add_argument("--reflection")
    create.add_argument("--translated")
    create.add_argument("--adapter")
    create.add_argument("--tool", action="append", default=[], help="Repeat name=version-or-source")
    create.add_argument("--command", action="append", default=[], help="Repeat exact tool command")
    create.add_argument("--deviation", action="append", default=[], help="Repeat category=description")
    create.add_argument("--anchor", help="Capture/event/pipeline anchor")
    create.add_argument("--note", action="append", default=[])
    create.add_argument(
        "--status",
        choices=["evidence-only", "translation-built", "runtime-validated"],
        default="evidence-only",
    )
    create.add_argument("--output", required=True)
    create.set_defaults(func=create_manifest)

    verify = sub.add_parser("verify", help="Verify all artifact hashes in a port manifest")
    verify.add_argument("manifest")
    verify.set_defaults(func=verify_manifest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
