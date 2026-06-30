#!/usr/bin/env python3
"""Plan and run PIX on Windows pixtool workflows for .wpix captures."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Iterable


DEFAULT_PIX_DIRS = [
    Path(r"C:\Program Files\Microsoft PIX"),
    Path(r"C:\Program Files (x86)\Microsoft PIX"),
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sanitize_label(value: str) -> str:
    import re

    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return label.strip("._") or "capture"


def dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def find_pixtool_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("PIXTOOL_PATH")
    if explicit:
        candidates.append(Path(explicit))

    for root in DEFAULT_PIX_DIRS:
        if root.is_dir():
            candidates.extend(sorted(root.glob("*/pixtool.exe"), reverse=True))

    path_candidate = shutil.which("pixtool.exe") or shutil.which("pixtool")
    if path_candidate:
        candidates.append(Path(path_candidate))

    return [path for path in dedupe_paths(candidates) if path.is_file()]


def require_pixtool(path: str | None = None, allow_missing: bool = False) -> Path:
    if path:
        candidate = Path(path)
        if candidate.is_file():
            return candidate
        if not allow_missing:
            raise FileNotFoundError(f"pixtool was not found: {candidate}")
        return candidate

    candidates = find_pixtool_candidates()
    if candidates:
        return candidates[0]
    if allow_missing:
        return Path("pixtool.exe")
    raise FileNotFoundError(
        "pixtool.exe was not found. Set PIXTOOL_PATH or install PIX on Windows."
    )


def command_line(argv: list[str]) -> str:
    return subprocess.list2cmdline(argv)


def path_arg(path: Path) -> str:
    return str(path)


def run(argv: list[str]) -> None:
    print(f"$ {command_line(argv)}")
    subprocess.run(argv, check=True)


def capture_label(capture: Path, label: str | None) -> str:
    return sanitize_label(label or capture.stem)


def analysis_paths(capture: Path, output_root: Path, label: str | None) -> dict[str, Path]:
    name = capture_label(capture, label)
    analysis_dir = output_root / name
    return {
        "analysis_dir": analysis_dir,
        "event_list": analysis_dir / "event-list.csv",
        "cpp_export": analysis_dir / "cpp-export",
        "index_output_dir": analysis_dir / "indexes",
        "index_report": analysis_dir
        / "indexes"
        / "cpp-export"
        / "pix_cpp_export_index.md",
        "index_json": analysis_dir
        / "indexes"
        / "cpp-export"
        / "pix_cpp_export_index.json",
    }


def event_list_args(args: argparse.Namespace) -> list[str]:
    result: list[str] = []
    for pattern in args.counters or []:
        result.append(f"--counters={pattern}")
    for pattern in args.counter_groups or []:
        result.append(f"--counter-groups={pattern}")
    if args.queue_name:
        result.append(f"--queue-name={args.queue_name}")
    return result


def export_args(args: argparse.Namespace) -> list[str]:
    result: list[str] = []
    if args.force:
        result.append("--force")
    if args.use_winpixeventruntime:
        result.append("--use-winpixeventruntime")
    if args.use_agilitysdk:
        result.append("--use-agilitySdk")
    if args.use_replay_time_executeindirect_buffers:
        result.append("--use-replay-time-executeindirect-buffers")
    return result


def open_capture_args(args: argparse.Namespace) -> list[str]:
    result: list[str] = []
    if getattr(args, "disable_gpu_plugins", False):
        result.append("--disable-gpu-plugins")
    if getattr(args, "enable_recreate_at_gpuva", False):
        result.append("--enable-recreate-at-gpuva")
    return result


def build_event_list_command(
    pixtool: Path, capture: Path, output: Path, args: argparse.Namespace
) -> list[str]:
    return [
        path_arg(pixtool),
        "open-capture",
        path_arg(capture),
        *open_capture_args(args),
        "save-event-list",
        path_arg(output),
        *event_list_args(args),
    ]


def build_export_cpp_command(
    pixtool: Path, capture: Path, output_dir: Path, args: argparse.Namespace
) -> list[str]:
    return [
        path_arg(pixtool),
        "open-capture",
        path_arg(capture),
        *open_capture_args(args),
        "export-to-cpp",
        *export_args(args),
        path_arg(output_dir),
    ]


def build_index_command(export_dir: Path, index_output_dir: Path) -> list[str]:
    return [
        sys.executable,
        path_arg(skill_root() / "scripts" / "pix_cpp_export_index.py"),
        "--pix-dir",
        path_arg(export_dir),
        "--label",
        "cpp-export",
        "--output-dir",
        path_arg(index_output_dir),
    ]


def build_save_resource_command(args: argparse.Namespace) -> list[str]:
    pixtool = require_pixtool(args.pixtool, allow_missing=not args.execute)
    capture = Path(args.capture)
    output = Path(args.output)
    command = [
        path_arg(pixtool),
        "open-capture",
        path_arg(capture),
        *open_capture_args(args),
        "save-resource",
        path_arg(output),
    ]
    if args.global_id is not None:
        command.append(f"--global-id={args.global_id}")
    if args.marker:
        command.append(f"--marker={args.marker}")
    if args.depth:
        command.append("--depth")
    elif args.rtv is not None:
        command.append(f"--rtv={args.rtv}")
    return command


def plan_prepare(args: argparse.Namespace) -> dict[str, Any]:
    capture = Path(args.capture)
    output_root = Path(args.output_root)
    paths = analysis_paths(capture, output_root, args.label)
    pixtool = require_pixtool(args.pixtool, allow_missing=not args.execute)

    commands: list[dict[str, Any]] = []
    if not args.skip_event_list:
        commands.append(
            {
                "name": "save-event-list",
                "argv": build_event_list_command(
                    pixtool, capture, paths["event_list"], args
                ),
            }
        )
    if not args.skip_export:
        commands.append(
            {
                "name": "export-to-cpp",
                "argv": build_export_cpp_command(
                    pixtool, capture, paths["cpp_export"], args
                ),
            }
        )
    if not args.skip_index:
        commands.append(
            {
                "name": "index-cpp-export",
                "argv": build_index_command(
                    paths["cpp_export"], paths["index_output_dir"]
                ),
            }
        )

    return {
        "capture": str(capture),
        "label": capture_label(capture, args.label),
        "pixtool": str(pixtool),
        "execute": args.execute,
        "paths": {key: str(value) for key, value in paths.items()},
        "commands": [
            {
                **command,
                "powershell": command_line(command["argv"]),
            }
            for command in commands
        ],
        "notes": [
            "save-resource can automate RTV and depth exports only.",
            "Arbitrary SRV/UAV texture export, arbitrary buffer export, and GUI resource history are not exposed by pixtool.",
        ],
    }


def execute_prepare(plan: dict[str, Any]) -> None:
    capture = Path(plan["capture"])
    if not capture.is_file():
        raise FileNotFoundError(f"capture does not exist: {capture}")

    paths = {key: Path(value) for key, value in plan["paths"].items()}
    paths["analysis_dir"].mkdir(parents=True, exist_ok=True)
    paths["event_list"].parent.mkdir(parents=True, exist_ok=True)
    paths["cpp_export"].parent.mkdir(parents=True, exist_ok=True)
    paths["index_output_dir"].mkdir(parents=True, exist_ok=True)

    for command in plan["commands"]:
        run(command["argv"])


def print_result(data: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, indent=2))
        return
    if "commands" in data:
        print(f"Capture: {data.get('capture', '')}")
        print(f"Label: {data.get('label', '')}")
        print(f"pixtool: {data.get('pixtool', '')}")
        print("Paths:")
        for key, value in data.get("paths", {}).items():
            print(f"  {key}: {value}")
        print("Commands:")
        for command in data["commands"]:
            print(f"  [{command['name']}] {command['powershell']}")
        if data.get("notes"):
            print("Notes:")
            for note in data["notes"]:
                print(f"  - {note}")
        return
    print(json.dumps(data, indent=2))


def command_discover(args: argparse.Namespace) -> int:
    candidates = find_pixtool_candidates()
    selected = require_pixtool(args.pixtool, allow_missing=True)
    data = {
        "selected": str(selected),
        "found": [str(path) for path in candidates],
        "env": {"PIXTOOL_PATH": os.environ.get("PIXTOOL_PATH", "")},
    }
    print_result(data, args.json)
    return 0


def command_capabilities(args: argparse.Namespace) -> int:
    data = {
        "supported": [
            "open .wpix captures",
            "export C++ replay projects",
            "save event lists as CSV",
            "save RTV resources from a selected event or marker",
            "save depth visualizations as PNG",
            "generate a C++ export index with PSO, command, and resource-reader anchors",
        ],
        "not_supported_by_pixtool_cli": [
            "arbitrary buffer export by resource id or name",
            "arbitrary SRV/UAV texture export by resource id or name",
            "GUI Resource History export",
            "custom PIX UI panels or menu plugins",
        ],
        "fallbacks": [
            "patch the C++ replay to add readback/dump code",
            "parse C++ export metadata and resources.bin with project-specific extractors",
            "ask for one manual PIX GUI export when the CLI has no equivalent",
        ],
    }
    print_result(data, args.json)
    return 0


def command_prepare(args: argparse.Namespace) -> int:
    plan = plan_prepare(args)
    if args.execute:
        execute_prepare(plan)
    print_result(plan, args.json)
    return 0


def command_event_list(args: argparse.Namespace) -> int:
    pixtool = require_pixtool(args.pixtool, allow_missing=not args.execute)
    capture = Path(args.capture)
    output = Path(args.output)
    command = build_event_list_command(pixtool, capture, output, args)
    data = {
        "capture": str(capture),
        "output": str(output),
        "execute": args.execute,
        "commands": [
            {
                "name": "save-event-list",
                "argv": command,
                "powershell": command_line(command),
            }
        ],
    }
    if args.execute:
        if not capture.is_file():
            raise FileNotFoundError(f"capture does not exist: {capture}")
        output.parent.mkdir(parents=True, exist_ok=True)
        run(command)
    print_result(data, args.json)
    return 0


def command_export_cpp(args: argparse.Namespace) -> int:
    pixtool = require_pixtool(args.pixtool, allow_missing=not args.execute)
    capture = Path(args.capture)
    output_dir = Path(args.output_dir)
    command = build_export_cpp_command(pixtool, capture, output_dir, args)
    data = {
        "capture": str(capture),
        "output_dir": str(output_dir),
        "execute": args.execute,
        "commands": [
            {
                "name": "export-to-cpp",
                "argv": command,
                "powershell": command_line(command),
            }
        ],
    }
    if args.execute:
        if not capture.is_file():
            raise FileNotFoundError(f"capture does not exist: {capture}")
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        run(command)
    print_result(data, args.json)
    return 0


def command_save_resource(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if args.depth and output.suffix.lower() != ".png":
        raise ValueError("pixtool depth save-resource output must be a .png file")
    command = build_save_resource_command(args)
    data = {
        "capture": args.capture,
        "output": args.output,
        "execute": args.execute,
        "resource_scope": "depth" if args.depth else "rtv",
        "commands": [
            {
                "name": "save-resource",
                "argv": command,
                "powershell": command_line(command),
            }
        ],
        "notes": [
            "This wraps pixtool save-resource, which targets RTV/depth resources from a draw call.",
            "It does not export arbitrary buffers or arbitrary SRV/UAV textures.",
        ],
    }
    if args.execute:
        capture = Path(args.capture)
        if not capture.is_file():
            raise FileNotFoundError(f"capture does not exist: {capture}")
        output.parent.mkdir(parents=True, exist_ok=True)
        run(command)
    print_result(data, args.json)
    return 0


def add_common_pixtool_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pixtool", help="Path to pixtool.exe. Overrides PIXTOOL_PATH.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")


def add_open_capture_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--disable-gpu-plugins",
        action="store_true",
        help="Pass --disable-gpu-plugins to open-capture.",
    )
    parser.add_argument(
        "--enable-recreate-at-gpuva",
        action="store_true",
        help="Pass --enable-recreate-at-gpuva to open-capture.",
    )


def add_event_list_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--counters",
        action="append",
        help="Counter pattern to include. Can be specified multiple times.",
    )
    parser.add_argument(
        "--counter-groups",
        action="append",
        help="Counter group pattern to include. Can be specified multiple times.",
    )
    parser.add_argument("--queue-name", help="Queue name for save-event-list.")


def add_export_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--force", action="store_true", help="Overwrite export files.")
    parser.add_argument(
        "--use-winpixeventruntime",
        action="store_true",
        help="Pass --use-winpixeventruntime to export-to-cpp.",
    )
    parser.add_argument(
        "--use-agilitysdk",
        action="store_true",
        help="Pass --use-agilitySdk to export-to-cpp.",
    )
    parser.add_argument(
        "--use-replay-time-executeindirect-buffers",
        action="store_true",
        help="Pass --use-replay-time-executeindirect-buffers to export-to-cpp.",
    )


def add_execute_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the command. Without this flag the script prints a dry-run plan.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    discover = sub.add_parser("discover", help="Find pixtool.exe candidates")
    add_common_pixtool_args(discover)
    discover.set_defaults(func=command_discover)

    capabilities = sub.add_parser("capabilities", help="Print automation boundaries")
    capabilities.add_argument("--json", action="store_true")
    capabilities.set_defaults(func=command_capabilities)

    prepare = sub.add_parser(
        "prepare",
        help="Plan or run event-list export, C++ export, and indexing for a .wpix capture",
    )
    add_common_pixtool_args(prepare)
    add_open_capture_args(prepare)
    add_event_list_args(prepare)
    add_export_args(prepare)
    add_execute_arg(prepare)
    prepare.add_argument("--capture", required=True, help="Path to a .wpix capture.")
    prepare.add_argument(
        "--output-root",
        default=".pix-analysis/pix-captures",
        help="Root directory for generated capture analysis artifacts.",
    )
    prepare.add_argument("--label", help="Stable label for output directories.")
    prepare.add_argument("--skip-event-list", action="store_true")
    prepare.add_argument("--skip-export", action="store_true")
    prepare.add_argument("--skip-index", action="store_true")
    prepare.set_defaults(func=command_prepare)

    event_list = sub.add_parser("event-list", help="Plan or run save-event-list")
    add_common_pixtool_args(event_list)
    add_open_capture_args(event_list)
    add_event_list_args(event_list)
    add_execute_arg(event_list)
    event_list.add_argument("--capture", required=True)
    event_list.add_argument("--output", required=True)
    event_list.set_defaults(func=command_event_list)

    export_cpp = sub.add_parser("export-cpp", help="Plan or run export-to-cpp")
    add_common_pixtool_args(export_cpp)
    add_open_capture_args(export_cpp)
    add_export_args(export_cpp)
    add_execute_arg(export_cpp)
    export_cpp.add_argument("--capture", required=True)
    export_cpp.add_argument("--output-dir", required=True)
    export_cpp.set_defaults(func=command_export_cpp)

    save_resource = sub.add_parser("save-resource", help="Plan or run save-resource")
    add_common_pixtool_args(save_resource)
    add_open_capture_args(save_resource)
    add_execute_arg(save_resource)
    save_resource.add_argument("--capture", required=True)
    save_resource.add_argument("--output", required=True)
    save_resource.add_argument("--global-id", type=int)
    save_resource.add_argument("--marker")
    group = save_resource.add_mutually_exclusive_group()
    group.add_argument("--rtv", type=int)
    group.add_argument("--depth", action="store_true")
    save_resource.set_defaults(func=command_save_resource)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
