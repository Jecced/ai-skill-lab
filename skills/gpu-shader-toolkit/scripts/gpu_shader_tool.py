#!/usr/bin/env python3
"""Unified command wrapper for local shader-analysis tools."""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parents[1]
TOOLS_DIR = REPO_ROOT / "vendor-tools" / "gpu-shader-toolkit"
LOCAL_TOOLCHAIN_PATH = TOOLS_DIR / "toolchain.local.json"


TOOL_COMMANDS = {
    "dxc": ["dxc"],
    "spirv-cross": ["spirv-cross"],
    "glslang": ["glslangValidator"],
    "spirv-dis": ["spirv-dis"],
    "spirv-val": ["spirv-val"],
    "spirv-as": ["spirv-as"],
    "spirv-opt": ["spirv-opt"],
    "dxil-spirv": ["dxil-spirv"],
}


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def exe_name(name: str) -> str:
    return name + ".exe" if is_windows() and not name.endswith(".exe") else name


def load_local_toolchain() -> dict:
    if not LOCAL_TOOLCHAIN_PATH.exists():
        return {"tools": {}}
    with LOCAL_TOOLCHAIN_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def candidates_from_local(tool_id: str) -> list[Path]:
    data = load_local_toolchain()
    entry = data.get("tools", {}).get(tool_id)
    if not entry:
        return []
    path = Path(entry.get("path", ""))
    return [path] if path.exists() else []


def candidates_from_skill_tools(command: str) -> list[Path]:
    name = exe_name(command)
    if not TOOLS_DIR.exists():
        return []
    return list(TOOLS_DIR.rglob(name))


def candidates_from_windows_sdk(command: str) -> list[Path]:
    if not is_windows() or command != "dxc":
        return []
    return [Path(p) for p in sorted(glob.glob("C:/Program Files (x86)/Windows Kits/10/bin/*/x64/dxc.exe"), reverse=True)]


def resolve_tool(tool_id: str) -> Path | None:
    commands = TOOL_COMMANDS.get(tool_id, [tool_id])
    for command in commands:
        for p in candidates_from_local(tool_id):
            if p.exists():
                return p
        for p in candidates_from_skill_tools(command):
            if p.exists():
                return p
        path_hit = shutil.which(exe_name(command)) or shutil.which(command)
        if path_hit:
            return Path(path_hit)
        for p in candidates_from_windows_sdk(command):
            if p.exists():
                return p
    return None


def run_tool(tool_id: str, args: list[str]) -> int:
    tool = resolve_tool(tool_id)
    if not tool:
        raise SystemExit(f"Tool not found: {tool_id}. Run setup_shader_tools.py hints or install/register the tool.")
    cmd = [str(tool), *args]
    print("+ " + " ".join(cmd))
    return subprocess.call(cmd)


def strip_remainder(args: list[str] | None) -> list[str]:
    if not args:
        return []
    return args[1:] if args[0] == "--" else args


def cmd_list(_: argparse.Namespace) -> int:
    for tool_id in TOOL_COMMANDS:
        tool = resolve_tool(tool_id)
        print(f"{tool_id}: {tool if tool else '<missing>'}")
    return 0


def cmd_dxc_dumpbin(args: argparse.Namespace) -> int:
    out = args.output
    if out is None:
        out = str(Path(args.input).with_suffix(Path(args.input).suffix + ".asm.txt"))
    return run_tool("dxc", ["-dumpbin", "-Fc", out, args.input])


def cmd_dxc_compile(args: argparse.Namespace) -> int:
    cmd = ["-T", args.target, "-E", args.entry, args.input]
    if args.output:
        cmd.extend(["-Fo", args.output])
    cmd.extend(strip_remainder(args.extra))
    return run_tool("dxc", cmd)


def cmd_spirv_cross(args: argparse.Namespace) -> int:
    cmd = [args.input]
    if args.reflect:
        cmd.append("--reflect")
    if args.hlsl:
        cmd.append("--hlsl")
    if args.msl:
        cmd.append("--msl")
    if args.glsl:
        cmd.append("--version")
        cmd.append(args.glsl)
    if args.output:
        cmd.extend(["--output", args.output])
    cmd.extend(strip_remainder(args.extra))
    return run_tool("spirv-cross", cmd)


def cmd_passthrough(tool_id: str, args: argparse.Namespace) -> int:
    return run_tool(tool_id, strip_remainder(args.args))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="List resolved tools")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("dxc-dumpbin", help="Dump DXIL/DXBC container/disassembly with dxc")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.set_defaults(func=cmd_dxc_dumpbin)

    p = sub.add_parser("dxc-compile", help="Compile HLSL with dxc")
    p.add_argument("input")
    p.add_argument("-T", "--target", required=True)
    p.add_argument("-E", "--entry", default="main")
    p.add_argument("-o", "--output")
    p.add_argument("extra", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_dxc_compile)

    p = sub.add_parser("spirv-cross", help="Run spirv-cross with common output modes")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("--reflect", action="store_true")
    p.add_argument("--hlsl", action="store_true")
    p.add_argument("--msl", action="store_true")
    p.add_argument("--glsl", metavar="VERSION")
    p.add_argument("extra", nargs=argparse.REMAINDER)
    p.set_defaults(func=cmd_spirv_cross)

    for name in ["glslang", "spirv-dis", "spirv-val", "spirv-as", "spirv-opt", "dxil-spirv"]:
        p = sub.add_parser(name, help=f"Pass through to {name}")
        p.add_argument("args", nargs=argparse.REMAINDER)
        p.set_defaults(func=lambda a, tool_id=name: cmd_passthrough(tool_id, a))

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
