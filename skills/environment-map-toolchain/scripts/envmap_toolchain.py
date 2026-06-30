#!/usr/bin/env python3
"""Discover and plan environment-map preprocessing commands."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable


TOOLS = {
    "cmft": [Path("cmft/cmftRelease64.exe"), Path("cmftRelease64.exe")],
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def candidate_roots() -> list[Path]:
    roots: list[Path] = []
    roots.append(repo_root() / "vendor-tools" / "environment-map")
    for name in ("ENVMAP_TOOLCHAIN_ROOT", "AI_SKILL_LAB_TOOL_ROOT", "VENDOR_TOOLS_ROOT"):
        value = os.environ.get(name)
        if value:
            roots.append(Path(value))
    return dedupe_paths(roots)


def discover() -> dict[str, object]:
    roots = candidate_roots()
    tools: dict[str, dict[str, object]] = {}
    for name, relatives in TOOLS.items():
        matches = []
        for root in roots:
            for rel in relatives:
                path = root / rel
                if path.is_file():
                    matches.append(str(path))
        tools[name] = {"found": bool(matches), "paths": matches}
    return {"roots": [str(root) for root in roots], "tools": tools}


def command_line(args: list[str]) -> str:
    return subprocess.list2cmdline(args)


def first_tool(name: str, discovered: dict[str, object]) -> str | None:
    data = discovered["tools"][name]  # type: ignore[index]
    paths = data["paths"]  # type: ignore[index]
    return paths[0] if paths else None


def plan(args: argparse.Namespace) -> dict[str, object]:
    found = discover()
    tool = first_tool("cmft", found)
    warnings = ["Confirm local cmft --help before execution; flags vary across builds."]
    commands: list[dict[str, object]] = []

    if tool:
        output_prefix = str(Path(args.output_prefix))
        cmd = [
            tool,
            "--input",
            str(Path(args.input)),
            "--filter",
            args.filter,
            "--srcFaceSize",
            str(args.source_size),
            "--dstFaceSize",
            str(args.size),
            "--mipCount",
            str(args.mips),
            "--output0",
            output_prefix,
            "--output0params",
            args.output_params,
        ]
        commands.append({"tool": "cmft", "argv": cmd, "powershell": command_line(cmd)})
    else:
        warnings.append("cmftRelease64.exe was not found.")

    return {
        "input": str(Path(args.input)),
        "output_prefix": str(Path(args.output_prefix)),
        "source_layout": args.source_layout,
        "filter": args.filter,
        "size": args.size,
        "mips": args.mips,
        "commands": commands,
        "warnings": warnings,
        "validation": [
            "Check face orientation in a viewer or runtime import path.",
            "Confirm mip count and roughness progression for radiance outputs.",
            "Check exposure/brightness against the source panorama.",
            "Inspect cube-edge seams.",
            "Record tool path, flags, source layout, face size, and output params.",
        ],
    }


def print_result(data: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2))
        return
    if "tools" in data:
        print("Search roots:")
        for root in data["roots"]:  # type: ignore[index]
            print(f"  {root}")
        print("\nTools:")
        for name, info in data["tools"].items():  # type: ignore[index]
            status = "found" if info["found"] else "missing"  # type: ignore[index]
            print(f"  {name}: {status}")
            for path in info["paths"]:  # type: ignore[index]
                print(f"    {path}")
    else:
        print(json.dumps(data, indent=2))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    discover_parser = sub.add_parser("discover", help="Find known environment-map tools")
    discover_parser.add_argument("--json", action="store_true")

    plan_parser = sub.add_parser("plan", help="Create a dry-run cmft command plan")
    plan_parser.add_argument("--input", required=True)
    plan_parser.add_argument("--output-prefix", required=True)
    plan_parser.add_argument("--source-layout", default="equirect", choices=["equirect", "cubemap", "hcross", "vcross", "faces"])
    plan_parser.add_argument("--filter", default="radiance", choices=["radiance", "irradiance", "none"])
    plan_parser.add_argument("--source-size", type=int, default=1024)
    plan_parser.add_argument("--size", type=int, default=256)
    plan_parser.add_argument("--mips", type=int, default=8)
    plan_parser.add_argument("--output-params", default="dds,bgra8,cubemap")
    plan_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "discover":
        print_result(discover(), args.json)
    elif args.cmd == "plan":
        print_result(plan(args), args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
