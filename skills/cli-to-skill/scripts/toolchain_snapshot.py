#!/usr/bin/env python3
"""Inspect local CLI/tool snapshots before turning them into skills."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import date
import heapq
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Iterable


EXECUTABLE_SUFFIXES = {
    ".exe",
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
    ".app",
}

ARCHIVE_SUFFIXES = {
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".xz",
}

PACKAGE_FILES = {
    "package.json",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "cargo.toml",
    "cmakelists.txt",
    "makefile",
    "pom.xml",
    "build.gradle",
}

HELP_ARGS = [["--help"], ["-h"], ["/?"]]
VERSION_ARGS = [["--version"], ["-v"], ["version"]]


@dataclass
class FileRecord:
    path: str
    size: int


def human_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def push_largest(heap: list[tuple[int, str]], size: int, path: str, limit: int) -> None:
    item = (size, path)
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif size > heap[0][0]:
        heapq.heapreplace(heap, item)


def safe_relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def is_executable_candidate(path: Path) -> bool:
    if path.suffix.lower() in EXECUTABLE_SUFFIXES:
        return True
    if os.name != "nt" and os.access(path, os.X_OK) and path.is_file():
        return True
    return False


def walk_files(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in {".git", "__pycache__", "node_modules"}]
        current_path = Path(current)
        for file_name in files:
            yield current_path / file_name


def scan_snapshot(root: Path, top: int) -> dict[str, object]:
    if not root.exists():
        raise FileNotFoundError(root)
    if not root.is_dir():
        raise NotADirectoryError(root)

    total_files = 0
    total_size = 0
    ext_counts: Counter[str] = Counter()
    ext_sizes: Counter[str] = Counter()
    top_level_counts: Counter[str] = Counter()
    top_level_sizes: Counter[str] = Counter()
    largest_files: list[tuple[int, str]] = []
    executables: list[tuple[int, str]] = []
    archives: list[tuple[int, str]] = []
    package_files: list[str] = []
    errors: list[str] = []

    for path in walk_files(root):
        try:
            stat = path.stat()
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            continue

        size = stat.st_size
        rel = safe_relative(path, root)
        total_files += 1
        total_size += size

        suffix = path.suffix.lower() or "<none>"
        ext_counts[suffix] += 1
        ext_sizes[suffix] += size

        first = rel.split("/", 1)[0]
        top_level_counts[first] += 1
        top_level_sizes[first] += size

        push_largest(largest_files, size, rel, top)
        if is_executable_candidate(path):
            push_largest(executables, size, rel, top)
        if suffix in ARCHIVE_SUFFIXES:
            push_largest(archives, size, rel, top)
        if path.name.lower() in PACKAGE_FILES:
            package_files.append(rel)

    top_entries = [
        {
            "path": name,
            "files": top_level_counts[name],
            "size": top_level_sizes[name],
            "size_human": human_size(top_level_sizes[name]),
        }
        for name, _ in top_level_sizes.most_common(top)
    ]

    extensions = [
        {
            "extension": ext,
            "files": ext_counts[ext],
            "size": ext_sizes[ext],
            "size_human": human_size(ext_sizes[ext]),
        }
        for ext, _ in ext_sizes.most_common(top)
    ]

    def heap_to_records(heap: list[tuple[int, str]]) -> list[dict[str, object]]:
        return [
            {"path": path, "size": size, "size_human": human_size(size)}
            for size, path in sorted(heap, reverse=True)
        ]

    return {
        "root": str(root),
        "total_files": total_files,
        "total_size": total_size,
        "total_size_human": human_size(total_size),
        "top_level_entries": top_entries,
        "largest_files": heap_to_records(largest_files),
        "largest_executables": heap_to_records(executables),
        "largest_archives": heap_to_records(archives),
        "largest_extensions": extensions,
        "package_files": sorted(package_files)[:top],
        "errors": errors[:top],
    }


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def scan_to_markdown(data: dict[str, object]) -> str:
    top_entries = data["top_level_entries"]  # type: ignore[index]
    largest_files = data["largest_files"]  # type: ignore[index]
    executables = data["largest_executables"]  # type: ignore[index]
    archives = data["largest_archives"]  # type: ignore[index]
    extensions = data["largest_extensions"]  # type: ignore[index]
    package_files = data["package_files"]  # type: ignore[index]

    parts = [
        "# Tool Snapshot Scan",
        "",
        f"Root: `{data['root']}`",
        f"Total files: {data['total_files']}",
        f"Total size: {data['total_size_human']}",
        "",
        "## Largest Top-Level Entries",
        markdown_table(
            ["Path", "Files", "Size"],
            [[item["path"], item["files"], item["size_human"]] for item in top_entries],
        ),
        "",
        "## Largest Files",
        markdown_table(
            ["Path", "Size"],
            [[item["path"], item["size_human"]] for item in largest_files],
        ),
        "",
        "## Executable Candidates",
        markdown_table(
            ["Path", "Size"],
            [[item["path"], item["size_human"]] for item in executables],
        ),
        "",
        "## Archive Candidates",
        markdown_table(
            ["Path", "Size"],
            [[item["path"], item["size_human"]] for item in archives],
        ),
        "",
        "## Largest File Types",
        markdown_table(
            ["Extension", "Files", "Size"],
            [[item["extension"], item["files"], item["size_human"]] for item in extensions],
        ),
    ]

    if package_files:
        parts.extend(["", "## Package Manifests", *[f"- `{path}`" for path in package_files]])

    errors = data["errors"]  # type: ignore[index]
    if errors:
        parts.extend(["", "## Scan Errors", *[f"- `{err}`" for err in errors]])

    return "\n".join(parts) + "\n"


def run_probe(tool: Path, mode: str, timeout: float, max_lines: int) -> dict[str, object]:
    if not tool.exists():
        raise FileNotFoundError(tool)
    if not tool.is_file():
        raise ValueError(f"not a file: {tool}")

    arg_sets = HELP_ARGS if mode == "help" else VERSION_ARGS
    attempts: list[dict[str, object]] = []

    for args in arg_sets:
        command = [str(tool), *args]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            lines = output.splitlines()[:max_lines]
            attempts.append(
                {
                    "argv": command,
                    "returncode": completed.returncode,
                    "timed_out": False,
                    "output": lines,
                }
            )
            if lines:
                break
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "")
            attempts.append(
                {
                    "argv": command,
                    "returncode": None,
                    "timed_out": True,
                    "output": output.splitlines()[:max_lines],
                }
            )
        except OSError as exc:
            attempts.append(
                {
                    "argv": command,
                    "returncode": None,
                    "timed_out": False,
                    "error": str(exc),
                    "output": [],
                }
            )

    return {
        "tool": str(tool),
        "mode": mode,
        "timeout_seconds": timeout,
        "attempts": attempts,
    }


def manifest_template(args: argparse.Namespace) -> str:
    today = date.today().isoformat()
    vendor_path = f"vendor-tools/{args.capability}"
    skill_path = f"skills/{args.skill_name or args.capability}"
    return f"""# Toolchain Promotion Manifest

Decision: promote | defer | dependency-only | discard
Capability name: {args.capability}
Source snapshot: {args.source_root}
Inspection date: {today}

## Workflow

- User-facing job:
- Repeated examples:
- Non-goals:

## Evidence

- Source product/version:
- Candidate entry points:
- Help/version probe:
- Minimal subset:
- Files intentionally excluded:
- License/redistribution:

## Repository Plan

- Skill path: `{skill_path}`
- Vendor path: `{vendor_path}`
- Required scripts:
- Required references:
- Environment overrides:

## Validation

- Discovery command:
- Dry-run command:
- Low-risk execution command:
- Expected output files:
- Known platform limits:
"""


def print_json(data: dict[str, object]) -> None:
    print(json.dumps(data, indent=2))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Read-only snapshot scan")
    scan.add_argument("--root", required=True, help="Tool snapshot directory")
    scan.add_argument("--top", type=int, default=12, help="Number of rows per summary")
    scan.add_argument("--markdown", action="store_true", help="Print Markdown instead of JSON")

    probe = sub.add_parser("probe", help="Run bounded help/version probes for trusted tools")
    probe.add_argument("--tool", required=True, help="Executable or script path")
    probe.add_argument("--mode", choices=["help", "version"], default="help")
    probe.add_argument("--timeout", type=float, default=5.0)
    probe.add_argument("--max-lines", type=int, default=80)

    manifest = sub.add_parser("manifest", help="Print a promotion manifest template")
    manifest.add_argument("--capability", required=True, help="Capability or vendor-tools folder name")
    manifest.add_argument("--source-root", required=True, help="Original source snapshot path")
    manifest.add_argument("--skill-name", help="Skill folder name; defaults to capability")

    args = parser.parse_args(argv)

    if args.command == "scan":
        data = scan_snapshot(Path(args.root).resolve(), args.top)
        if args.markdown:
            print(scan_to_markdown(data))
        else:
            print_json(data)
        return 0

    if args.command == "probe":
        print_json(run_probe(Path(args.tool).resolve(), args.mode, args.timeout, args.max_lines))
        return 0

    if args.command == "manifest":
        print(manifest_template(args))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
