#!/usr/bin/env python3
"""Discover Android platform-tools and generate safe adb command plans."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable


TOOLS = {
    "adb": {"windows": "adb.exe", "other": "adb"},
    "fastboot": {"windows": "fastboot.exe", "other": "fastboot"},
    "sqlite3": {"windows": "sqlite3.exe", "other": "sqlite3"},
    "etc1tool": {"windows": "etc1tool.exe", "other": "etc1tool"},
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def is_windows() -> bool:
    return os.name == "nt"


def dedupe(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower() if is_windows() else str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def candidate_roots() -> list[Path]:
    roots: list[Path] = [repo_root() / "vendor-tools" / "adb" / "platform-tools"]

    for env_name in ("ADB_PLATFORM_TOOLS_ROOT", "ANDROID_PLATFORM_TOOLS_ROOT"):
        value = os.environ.get(env_name)
        if value:
            roots.append(Path(value))

    for env_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(env_name)
        if value:
            roots.append(Path(value) / "platform-tools")

    path_value = os.environ.get("PATH", "")
    for part in path_value.split(os.pathsep):
        if part:
            roots.append(Path(part))

    return dedupe(roots)


def tool_name(name: str) -> str:
    data = TOOLS[name]
    return data["windows"] if is_windows() else data["other"]


def discover_tools() -> dict[str, object]:
    roots = candidate_roots()
    tools: dict[str, dict[str, object]] = {}
    for name in TOOLS:
        matches: list[str] = []
        exe_name = tool_name(name)
        for root in roots:
            path = root / exe_name
            if path.is_file():
                matches.append(str(path))
        tools[name] = {"found": bool(matches), "paths": matches}

    source_properties = []
    for root in roots:
        path = root / "source.properties"
        if path.is_file():
            source_properties.append(str(path))

    return {
        "platform": "windows" if is_windows() else sys.platform,
        "roots": [str(root) for root in roots],
        "tools": tools,
        "source_properties": source_properties,
    }


def first_tool(name: str, discovered: dict[str, object] | None = None) -> str | None:
    data = discovered or discover_tools()
    tool_data = data["tools"][name]  # type: ignore[index]
    paths = tool_data["paths"]  # type: ignore[index]
    return paths[0] if paths else None


def command_line(args: list[str]) -> str:
    return subprocess.list2cmdline(args)


def run_command(args: list[str], timeout: float = 10.0) -> dict[str, object]:
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    return {
        "argv": args,
        "powershell": command_line(args),
        "returncode": completed.returncode,
        "stdout": completed.stdout.splitlines(),
        "stderr": completed.stderr.splitlines(),
    }


def tool_versions() -> dict[str, object]:
    discovered = discover_tools()
    versions: dict[str, object] = {}

    adb = first_tool("adb", discovered)
    if adb:
        versions["adb"] = run_command([adb, "--version"])
    else:
        versions["adb"] = {"missing": True}

    fastboot = first_tool("fastboot", discovered)
    if fastboot:
        versions["fastboot"] = run_command([fastboot, "--version"])
    else:
        versions["fastboot"] = {"missing": True}

    source_properties = []
    for path_text in discovered["source_properties"]:  # type: ignore[index]
        path = Path(path_text)
        source_properties.append({"path": path_text, "text": path.read_text(encoding="utf-8").splitlines()})

    return {"discovered": discovered, "versions": versions, "source_properties": source_properties}


def adb_devices() -> dict[str, object]:
    adb = first_tool("adb")
    if not adb:
        return {"error": "adb was not found", "discovered": discover_tools()}
    return run_command([adb, "devices", "-l"])


def serial_args(serial: str | None) -> list[str]:
    return ["-s", serial] if serial else []


def plan_common(args: argparse.Namespace, adb_subcommand: list[str], risk: str, notes: list[str]) -> dict[str, object]:
    discovered = discover_tools()
    adb = first_tool("adb", discovered)
    command = [adb or "adb", *serial_args(args.serial), *adb_subcommand]
    return {
        "risk": risk,
        "serial": args.serial,
        "argv": command,
        "powershell": command_line(command),
        "notes": notes,
        "discovered": discovered,
    }


def plan_logcat(args: argparse.Namespace) -> dict[str, object]:
    cmd = ["logcat", "-v", args.format]
    if args.dump:
        cmd.append("-d")
    for tag in args.tag:
        cmd.append(tag if ":" in tag else f"{tag}:D")
    if args.tag:
        cmd.append("*:S")
    notes = ["Logcat can contain private URLs, package names, tokens, and device identifiers."]
    if args.output:
        notes.append(f"Redirect output to: {args.output}")
    return plan_common(args, cmd, "read-only privacy-sensitive", notes)


def plan_screenshot(args: argparse.Namespace) -> dict[str, object]:
    cmd = ["exec-out", "screencap", "-p"]
    return plan_common(args, cmd, "read-only privacy-sensitive", [f"Redirect binary output to: {args.output}"])


def plan_bugreport(args: argparse.Namespace) -> dict[str, object]:
    return plan_common(
        args,
        ["bugreport", args.output],
        "read-only privacy-sensitive",
        ["Bugreports can contain extensive device, account, app, and path information."],
    )


def plan_install(args: argparse.Namespace) -> dict[str, object]:
    cmd = ["install"]
    if args.replace:
        cmd.append("-r")
    if args.grant_runtime_permissions:
        cmd.append("-g")
    cmd.append(str(Path(args.apk)))
    return plan_common(args, cmd, "state-changing", ["Installs or updates an APK on the target device."])


def plan_uninstall(args: argparse.Namespace) -> dict[str, object]:
    cmd = ["uninstall"]
    if args.keep_data:
        cmd.append("-k")
    cmd.append(args.package)
    return plan_common(args, cmd, "state-changing", ["Removes the package from the target device."])


def print_result(data: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2))
        return
    print(json.dumps(data, indent=2))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("discover", help="Find adb, fastboot, and related tools")
    sub.add_parser("version", help="Print adb/fastboot versions and source.properties")
    sub.add_parser("devices", help="Run adb devices -l")

    logcat = sub.add_parser("plan-logcat", help="Plan a logcat command")
    logcat.add_argument("--serial")
    logcat.add_argument("--format", default="threadtime")
    logcat.add_argument("--tag", action="append", default=[])
    logcat.add_argument("--dump", action="store_true", help="Use -d to dump and exit")
    logcat.add_argument("--output")

    screenshot = sub.add_parser("plan-screenshot", help="Plan a screenshot command")
    screenshot.add_argument("--serial")
    screenshot.add_argument("--output", required=True)

    bugreport = sub.add_parser("plan-bugreport", help="Plan a bugreport command")
    bugreport.add_argument("--serial")
    bugreport.add_argument("--output", required=True)

    install = sub.add_parser("plan-install", help="Plan an APK install command")
    install.add_argument("--serial")
    install.add_argument("--apk", required=True)
    install.add_argument("--replace", action="store_true", default=True)
    install.add_argument("--grant-runtime-permissions", action="store_true")

    uninstall = sub.add_parser("plan-uninstall", help="Plan an uninstall command")
    uninstall.add_argument("--serial")
    uninstall.add_argument("--package", required=True)
    uninstall.add_argument("--keep-data", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd == "discover":
        print_result(discover_tools(), args.json)
    elif args.cmd == "version":
        print_result(tool_versions(), args.json)
    elif args.cmd == "devices":
        print_result(adb_devices(), args.json)
    elif args.cmd == "plan-logcat":
        print_result(plan_logcat(args), args.json)
    elif args.cmd == "plan-screenshot":
        print_result(plan_screenshot(args), args.json)
    elif args.cmd == "plan-bugreport":
        print_result(plan_bugreport(args), args.json)
    elif args.cmd == "plan-install":
        print_result(plan_install(args), args.json)
    elif args.cmd == "plan-uninstall":
        print_result(plan_uninstall(args), args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
