#!/usr/bin/env python3
"""Discover and plan texture toolchain commands.

The script is intentionally dry-run oriented. It finds known tools and emits
command candidates, leaving uncommon encoder flags for explicit review.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable


TOOLS = {
    "astcenc": [
        Path("astc-encoder/astcenc.exe"),
        Path("mali_win32/astcenc.exe"),
        Path("astcenc.exe"),
    ],
    "etcpack": [Path("mali_win32/etcpack.exe"), Path("etcpack.exe")],
    "mali_convert": [Path("mali_win32/convert.exe"), Path("convert.exe")],
    "mali_composite": [Path("mali_win32/composite.exe"), Path("composite.exe")],
    "pvrtex": [Path("PVRTexTool_win32/PVRTexToolCLI.exe"), Path("PVRTexToolCLI.exe")],
    "pvr_compare": [Path("PVRTexTool_win32/compare.exe"), Path("compare.exe")],
    "cwebp": [Path("libwebp_win32/bin/cwebp.exe"), Path("cwebp.exe")],
    "dwebp": [Path("libwebp_win32/bin/dwebp.exe"), Path("dwebp.exe")],
    "webpinfo": [Path("libwebp_win32/bin/webpinfo.exe"), Path("webpinfo.exe")],
    "webpmux": [Path("libwebp_win32/bin/webpmux.exe"), Path("webpmux.exe")],
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def candidate_roots() -> list[Path]:
    roots: list[Path] = []
    roots.append(repo_root() / "vendor-tools" / "texture-compression")
    for name in ("TEXTURE_TOOLCHAIN_ROOT", "AI_SKILL_LAB_TOOL_ROOT", "VENDOR_TOOLS_ROOT"):
        value = os.environ.get(name)
        if value:
            roots.append(Path(value))
    return dedupe_paths(roots)


def dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


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


def quality_value(quality: str) -> int:
    return {"low": 60, "normal": 80, "high": 90, "lossless": 100}[quality]


def astc_quality_flag(quality: str) -> str:
    return {
        "low": "-fast",
        "normal": "-medium",
        "high": "-thorough",
        "lossless": "-exhaustive",
    }[quality]


def plan(args: argparse.Namespace) -> dict[str, object]:
    found = discover()
    fmt = args.format
    input_path = str(Path(args.input))
    output_path = str(Path(args.output))
    warnings: list[str] = []
    commands: list[dict[str, object]] = []

    if fmt == "webp":
        tool = first_tool("cwebp", found)
        if tool:
            cmd = [tool]
            if args.quality == "lossless":
                cmd.append("-lossless")
            else:
                cmd += ["-q", str(quality_value(args.quality))]
            cmd += [input_path, "-o", output_path]
            commands.append({"tool": "cwebp", "argv": cmd, "powershell": command_line(cmd)})
        else:
            warnings.append("cwebp was not found.")
    elif fmt == "decode-webp":
        tool = first_tool("dwebp", found)
        if tool:
            cmd = [tool, input_path, "-o", output_path]
            commands.append({"tool": "dwebp", "argv": cmd, "powershell": command_line(cmd)})
        else:
            warnings.append("dwebp was not found.")
    elif fmt == "astc":
        tool = first_tool("astcenc", found)
        if tool:
            cmd = [tool, "-cl", input_path, output_path, args.block, astc_quality_flag(args.quality)]
            commands.append({"tool": "astcenc", "argv": cmd, "powershell": command_line(cmd)})
        else:
            warnings.append("astcenc was not found.")
    elif fmt in {"pvrtc", "etc"}:
        tool = first_tool("pvrtex", found) or first_tool("etcpack", found)
        warnings.append(f"{fmt} flags vary by encoder version. Confirm local help before executing.")
        if tool:
            commands.append(
                {
                    "tool": Path(tool).name,
                    "argv": [tool, "<confirm-flags>", input_path, output_path],
                    "powershell": command_line([tool, "<confirm-flags>", input_path, output_path]),
                }
            )
        else:
            warnings.append("No PVRTexToolCLI or etcpack candidate was found.")

    return {
        "format": fmt,
        "input": input_path,
        "output": output_path,
        "quality": args.quality,
        "commands": commands,
        "warnings": warnings,
        "validation": [
            "Confirm output file exists and source file is unchanged.",
            "Confirm dimensions and alpha behavior match the request.",
            "Visually inspect important color, UI, normal, and mask textures.",
            "Record encoder, flags, and source path for reproducibility.",
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

    discover_parser = sub.add_parser("discover", help="Find known texture tools")
    discover_parser.add_argument("--json", action="store_true")

    plan_parser = sub.add_parser("plan", help="Create a dry-run command plan")
    plan_parser.add_argument("--input", required=True)
    plan_parser.add_argument("--output", required=True)
    plan_parser.add_argument("--format", choices=["astc", "webp", "decode-webp", "pvrtc", "etc"], required=True)
    plan_parser.add_argument("--quality", choices=["low", "normal", "high", "lossless"], default="normal")
    plan_parser.add_argument("--block", default="6x6", help="ASTC block size, for example 4x4, 6x6, or 8x8")
    plan_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "discover":
        print_result(discover(), args.json)
    elif args.cmd == "plan":
        print_result(plan(args), args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
