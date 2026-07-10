#!/usr/bin/env python3
"""Build a selected-event pass graph and verify RenderDoc evidence artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


NULL_IDS = {"", "ResourceId::0", "ResourceId()", "None", "null"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resource_id(descriptor: dict[str, Any] | None) -> str:
    return str((descriptor or {}).get("resource", ""))


def valid_resource(value: str) -> bool:
    return value not in NULL_IDS


def event_resources(event: dict[str, Any]) -> tuple[set[str], set[str]]:
    inputs: set[str] = set()
    outputs: set[str] = set()
    for target in event.get("outputTargets", []):
        value = resource_id(target)
        if valid_resource(value):
            outputs.add(value)
    depth = resource_id(event.get("depthTarget"))
    if valid_resource(depth):
        outputs.add(depth)
    for stage in event.get("stages", {}).values():
        for category in ["constantBlocks", "readOnlyResources", "readWriteResources"]:
            for binding in stage.get(category, []):
                value = resource_id(binding.get("descriptor"))
                if valid_resource(value):
                    inputs.add(value)
                    if category == "readWriteResources":
                        outputs.add(value)
    return inputs, outputs


def build_graph(events: list[dict[str, Any]]) -> dict[str, Any]:
    latest_producer: dict[str, int] = {}
    edges: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for event in events:
        eid = int(event.get("eventId", -1))
        if event.get("error"):
            summaries.append({"eventId": eid, "error": event["error"]})
            continue
        inputs, outputs = event_resources(event)
        for value in sorted(inputs):
            producer = latest_producer.get(value)
            if producer is None:
                unresolved.append({"eventId": eid, "resourceId": value})
            elif producer != eid:
                edges.append({"producerEvent": producer, "consumerEvent": eid, "resourceId": value})
        summaries.append(
            {
                "eventId": eid,
                "graphicsPipelineObject": event.get("graphicsPipelineObject"),
                "computePipelineObject": event.get("computePipelineObject"),
                "stages": sorted(event.get("stages", {}).keys()),
                "inputs": sorted(inputs),
                "outputs": sorted(outputs),
            }
        )
        for value in outputs:
            latest_producer[value] = eid
    return {"events": summaries, "edges": edges, "unresolvedInputs": unresolved}


def walk_artifacts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and ("sha256" in value or "missing" in value or "error" in value):
            yield value
        for child in value.values():
            yield from walk_artifacts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_artifacts(child)


def resolve_artifact(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def verify_artifacts(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    checked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for artifact in walk_artifacts(manifest):
        raw_path = str(artifact["path"])
        path = resolve_artifact(root, raw_path).resolve()
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        record: dict[str, Any] = {"path": raw_path, "resolvedPath": str(path)}
        if artifact.get("error"):
            record.update({"status": "export-error", "error": artifact["error"]})
        elif artifact.get("missing") or not path.is_file():
            record["status"] = "missing"
        else:
            expected = artifact.get("sha256")
            actual = sha256_file(path) if expected else None
            record.update(
                {
                    "status": "pass" if not expected or actual == expected else "hash-mismatch",
                    "bytes": path.stat().st_size,
                    "expectedSha256": expected,
                    "actualSha256": actual,
                }
            )
        checked.append(record)
    counts: dict[str, int] = {}
    for record in checked:
        counts[record["status"]] = counts.get(record["status"], 0) + 1
    return {"counts": counts, "artifacts": checked}


def markdown_report(report: dict[str, Any]) -> str:
    graph = report["graph"]
    lines = [
        "# RenderDoc Evidence Report",
        "",
        f"- Capture: `{report.get('capture', '')}`",
        f"- API: `{report.get('api', {}).get('pipelineType', 'unknown')}`",
        f"- Selected events: `{', '.join(str(value) for value in report.get('targetEids', []))}`",
        "",
        "## Selected Events",
        "",
        "| EID | Stages | Inputs | Outputs |",
        "| ---: | --- | ---: | ---: |",
    ]
    for event in graph["events"]:
        if event.get("error"):
            lines.append(f"| {event['eventId']} | error | 0 | 0 |")
        else:
            lines.append(
                f"| {event['eventId']} | {', '.join(event['stages']) or '-'} | {len(event['inputs'])} | {len(event['outputs'])} |"
            )
    lines.extend(["", "## Producer / Consumer Edges", ""])
    if graph["edges"]:
        lines.extend(["| Producer | Consumer | Resource |", "| ---: | ---: | --- |"])
        for edge in graph["edges"]:
            lines.append(f"| {edge['producerEvent']} | {edge['consumerEvent']} | `{edge['resourceId']}` |")
    else:
        lines.append("No selected-event resource edges were resolved.")
    verification = report.get("verification")
    if verification:
        lines.extend(["", "## Artifact Verification", ""])
        for status, count in sorted(verification["counts"].items()):
            lines.append(f"- {status}: {count}")
    lines.extend(
        [
            "",
            "## Interpretation Boundary",
            "",
            "This graph only connects selected events through captured resource IDs. Assign pass semantics only after checking shader access, formats, contents, and surrounding events.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    parser.add_argument("--verify-artifacts", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).expanduser().resolve()
    manifest = load_json(manifest_path)
    output_root = manifest_path.parent
    report: dict[str, Any] = {
        "schema": 1,
        "capture": manifest.get("capture"),
        "api": manifest.get("api", {}),
        "targetEids": manifest.get("targetEids", []),
        "graph": build_graph(manifest.get("events", [])),
    }
    if args.verify_artifacts:
        report["verification"] = verify_artifacts(manifest, output_root)
    json_out = Path(args.json_out).resolve() if args.json_out else output_root / "capture_evidence_report.json"
    markdown_out = Path(args.markdown_out).resolve() if args.markdown_out else output_root / "capture_evidence_report.md"
    write_json(json_out, report)
    markdown_out.write_text(markdown_report(report), encoding="utf-8", newline="\n")
    print(json.dumps({"json": str(json_out), "markdown": str(markdown_out)}, indent=2))
    verification = report.get("verification", {}).get("counts", {})
    failed = sum(verification.get(key, 0) for key in ["missing", "hash-mismatch", "export-error"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
