#!/usr/bin/env python3
"""Discover, diagnose, install, and plan RenderDoc MCP evidence workflows."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Iterable
from urllib.request import Request, urlopen
import zipfile


PRIMARY_REPO = "JiaboLi-GitHub/renderdoc-mcp"
REFERENCE_REPO = "Linkingooo/renderdoc-mcp"
GITHUB_API = "https://api.github.com/repos"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_install_dir() -> Path:
    return repo_root() / "vendor-tools" / "renderdoc-mcp"


def codex_import_dir() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "vendor_imports" / "renderdoc-mcp"


def is_windows() -> bool:
    return os.name == "nt"


def exe_name(base: str) -> str:
    return f"{base}.exe" if is_windows() else base


def command_line(args: list[str]) -> str:
    return subprocess.list2cmdline(args)


def http_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "ai-skill-lab-renderdoc-mcp-skill"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def download_file(url: str, output: Path) -> None:
    request = Request(url, headers={"User-Agent": "ai-skill-lab-renderdoc-mcp-skill"})
    output.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(request, timeout=120) as response, output.open("wb") as stream:
        shutil.copyfileobj(response, stream)


def release_for(repo: str, tag: str | None = None) -> dict[str, object]:
    suffix = "releases/latest" if not tag or tag == "latest" else f"releases/tags/{tag}"
    return http_json(f"{GITHUB_API}/{repo}/{suffix}")


def slim_release(repo: str, tag: str | None = None) -> dict[str, object]:
    release = release_for(repo, tag)
    assets = release.get("assets", [])
    return {
        "repo": repo,
        "tag": release.get("tag_name"),
        "name": release.get("name"),
        "published_at": release.get("published_at"),
        "html_url": release.get("html_url"),
        "assets": [
            {
                "name": asset.get("name"),
                "size": asset.get("size"),
                "browser_download_url": asset.get("browser_download_url"),
            }
            for asset in assets
            if isinstance(asset, dict)
        ],
    }


def repo_metadata(repo: str) -> dict[str, object]:
    data = http_json(f"{GITHUB_API}/{repo}")
    return {
        "repo": repo,
        "description": data.get("description"),
        "pushed_at": data.get("pushed_at"),
        "updated_at": data.get("updated_at"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "default_branch": data.get("default_branch"),
        "language": data.get("language"),
        "html_url": data.get("html_url"),
    }


def dedupe(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower() if is_windows() else str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def path_parts() -> list[Path]:
    return [Path(part) for part in os.environ.get("PATH", "").split(os.pathsep) if part]


def kind_settings(kind: str) -> tuple[str, str]:
    settings = {
        "server": ("RENDERDOC_MCP_PATH", "renderdoc-mcp"),
        "cli": ("RENDERDOC_CLI_PATH", "renderdoc-cli"),
        "qrenderdoc": ("QRENDERDOC_PATH", "qrenderdoc"),
    }
    return settings[kind]


def executable_candidates(kind: str) -> list[Path]:
    env_name, base = kind_settings(kind)
    binary = exe_name(base)
    install_dir = Path(os.environ.get("RENDERDOC_MCP_HOME", default_install_dir()))
    candidates: list[Path] = []
    if os.environ.get(env_name):
        candidates.append(Path(os.environ[env_name]))
    candidates.extend(
        [
            install_dir / "bin" / binary,
            install_dir / binary,
            default_install_dir() / "bin" / binary,
            default_install_dir() / binary,
            codex_import_dir() / "bin" / binary,
            codex_import_dir() / binary,
        ]
    )
    candidates.extend(part / binary for part in path_parts())
    if is_windows():
        for value in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]:
            if value:
                candidates.append(Path(value) / "RenderDoc" / binary)
    return dedupe(candidates)


def existing(paths: Iterable[Path]) -> list[str]:
    return [str(path.resolve()) for path in paths if path.is_file()]


def runtime_candidates() -> list[Path]:
    candidates: list[Path] = []
    if os.environ.get("RENDERDOC_RUNTIME_DIR"):
        candidates.append(Path(os.environ["RENDERDOC_RUNTIME_DIR"]))
    install_dir = Path(os.environ.get("RENDERDOC_MCP_HOME", default_install_dir()))
    candidates.extend([install_dir / "bin", install_dir, codex_import_dir() / "bin", codex_import_dir()])
    if is_windows():
        for value in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]:
            if value:
                root = Path(value)
                candidates.extend([root / "RenderDoc", *root.glob("RenderDoc*")])
    return dedupe(candidates)


def has_runtime(path: Path) -> bool:
    names = ["renderdoc.dll", "renderdoc.pyd", "renderdoc.so", "librenderdoc.so", "renderdoc.json"]
    return any((path / name).exists() for name in names)


def discover() -> dict[str, object]:
    result: dict[str, object] = {}
    for kind in ["server", "cli", "qrenderdoc"]:
        candidates = executable_candidates(kind)
        result[kind] = {
            "candidates": [str(path) for path in candidates],
            "paths": existing(candidates),
        }
    runtime_dirs = runtime_candidates()
    result["runtime"] = {
        "candidates": [str(path) for path in runtime_dirs],
        "paths": [str(path.resolve()) for path in runtime_dirs if path.is_dir() and has_runtime(path)],
    }
    return result


def first_path(kind: str) -> str | None:
    paths = discover()[kind]["paths"]  # type: ignore[index]
    return paths[0] if paths else None


def platform_tokens() -> list[str]:
    if is_windows():
        return ["win", "windows", "x64"]
    if sys.platform == "darwin":
        return ["mac", "osx", "darwin"]
    return ["linux", "x64"]


def choose_archive_asset(release: dict[str, object], requested: str | None = None) -> dict[str, object] | None:
    assets = [asset for asset in release.get("assets", []) if isinstance(asset, dict)]
    if requested:
        return next((asset for asset in assets if asset.get("name") == requested), None)
    archives = [
        asset
        for asset in assets
        if str(asset.get("name", "")).lower().endswith((".zip", ".tar.gz", ".tgz"))
    ]
    if not archives:
        return None
    scored = []
    for asset in archives:
        name = str(asset.get("name", "")).lower()
        score = sum(1 for token in platform_tokens() if token in name)
        scored.append((score, name, asset))
    scored.sort(reverse=True, key=lambda item: item[0])
    return scored[0][2]


def safe_extract_zip(archive: Path, destination: Path) -> None:
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (root / member.filename).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"refusing to extract outside destination: {member.filename}") from exc
        zf.extractall(root)


def validate_install_dir(path: Path) -> None:
    resolved = path.resolve()
    anchor = Path(resolved.anchor).resolve()
    if resolved in {anchor, Path.home().resolve(), repo_root()}:
        raise ValueError(f"refusing unsafe install directory: {resolved}")
    if "renderdoc" not in resolved.name.lower() and "renderdoc" not in str(resolved.parent).lower():
        raise ValueError(f"install directory must be clearly scoped to renderdoc-mcp: {resolved}")


def install_release(args: argparse.Namespace) -> dict[str, object]:
    release = slim_release(PRIMARY_REPO, args.tag)
    asset = choose_archive_asset(release, args.asset)
    if not asset:
        return {
            "error": "no archive release asset was found",
            "repo": PRIMARY_REPO,
            "tag": release.get("tag"),
            "assets": release.get("assets", []),
            "fallback": "Use an existing install or build upstream outside this skill.",
        }
    name = str(asset["name"])
    url = str(asset["browser_download_url"])
    if not name.lower().endswith(".zip"):
        return {"error": "only .zip release archives are supported", "asset": asset}
    install_dir = Path(args.install_dir).resolve() if args.install_dir else default_install_dir()
    validate_install_dir(install_dir)
    if install_dir.exists() and not args.force:
        return {"error": "install directory exists; pass --force to replace it", "install_dir": str(install_dir)}
    with tempfile.TemporaryDirectory(prefix="renderdoc-mcp-release-") as tmp:
        archive = Path(tmp) / name
        download_file(url, archive)
        if install_dir.exists():
            shutil.rmtree(install_dir)
        install_dir.mkdir(parents=True, exist_ok=True)
        safe_extract_zip(archive, install_dir)
    if not is_windows():
        for binary in install_dir.rglob("renderdoc-*"):
            if binary.is_file():
                binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    metadata = {
        "repo": PRIMARY_REPO,
        "tag": release.get("tag"),
        "asset": name,
        "asset_url": url,
        "install_dir": str(install_dir),
    }
    (install_dir / "VERSION.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return {"installed": metadata, "discover": discover()}


def risk_for(parts: list[str]) -> str:
    lowered = [part.lower() for part in parts]
    if not lowered or lowered[0] in {"--help", "-h", "help", "version", "--version"}:
        return "low"
    joined = " ".join(lowered)
    if any(token in joined for token in ["inject", "attach", "launch", "remote", "capture-live", "live-capture"]):
        return "high-risk-live-capture"
    if any(token in joined for token in ["export", "dump", "save", "snapshot", "screenshot"]):
        return "review-writes-output"
    if any(token in joined for token in ["info", "list", "open", "inspect", "state", "pipeline", "shader", "resource"]):
        return "low-or-read-only"
    return "review"


def plan(args: argparse.Namespace, command_parts: list[str]) -> dict[str, object]:
    kind = "server" if args.server else "cli"
    _, base = kind_settings(kind)
    executable = first_path(kind) or exe_name(base)
    command = [executable, *command_parts]
    return {
        "kind": kind,
        "risk": risk_for(command_parts),
        "argv": command,
        "powershell": command_line(command),
        "notes": [
            "Prefer an existing authorized .rdc before live capture.",
            "Write large exports to an explicit analysis directory.",
            "Do not use this workflow for stealth injection or bypass requests.",
        ],
        "discover": discover(),
    }


def bounded_run(command: list[str], timeout: int) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "argv": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-20000:],
            "stderr": completed.stderr[-20000:],
            "timedOut": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "argv": command,
            "returncode": None,
            "stdout": (exc.stdout or "")[-20000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-20000:] if isinstance(exc.stderr, str) else "",
            "timedOut": True,
        }


def replay_classification(probe: dict[str, object]) -> str:
    text = f"{probe.get('stdout', '')}\n{probe.get('stderr', '')}".lower()
    if probe.get("timedOut"):
        return "timeout"
    if probe.get("returncode") == 0:
        return "compatible"
    if "newer incompatible version" in text or "newer incompatible" in text:
        return "capture-newer-than-runtime"
    if "failed to open replay" in text:
        return "replay-open-failed"
    if "transport closed" in text:
        return "mcp-transport-closed"
    return "failed"


def doctor(args: argparse.Namespace) -> dict[str, object]:
    found = discover()
    server_paths = found["server"]["paths"]  # type: ignore[index]
    cli_paths = found["cli"]["paths"]  # type: ignore[index]
    runtime_paths = found["runtime"]["paths"]  # type: ignore[index]
    layers: list[dict[str, object]] = [
        {"layer": "server-files", "status": "pass" if server_paths else "unresolved", "paths": server_paths},
        {"layer": "cli-files", "status": "pass" if cli_paths else "unresolved", "paths": cli_paths},
        {"layer": "replay-runtime", "status": "pass" if runtime_paths else "unresolved", "paths": runtime_paths},
        {
            "layer": "client-exposure-and-transport",
            "status": "not-checked",
            "next": "Verify the current MCP namespace and call a lightweight tool such as get_capture_info.",
        },
    ]
    result: dict[str, object] = {"discover": found, "layers": layers}
    if not args.capture:
        return result
    capture = Path(args.capture).expanduser().resolve()
    capture_layer: dict[str, object] = {
        "layer": "capture-file",
        "status": "pass" if capture.is_file() else "fail",
        "path": str(capture),
        "bytes": capture.stat().st_size if capture.is_file() else None,
    }
    layers.append(capture_layer)
    if not capture.is_file():
        return result
    if not cli_paths:
        layers.append({"layer": "capture-replay", "status": "unresolved", "reason": "renderdoc-cli was not found"})
        return result
    probe = bounded_run([cli_paths[0], str(capture), "info"], args.timeout)
    classification = replay_classification(probe)
    layers.append(
        {
            "layer": "capture-replay",
            "status": "pass" if classification == "compatible" else "fail",
            "classification": classification,
            "probe": probe,
        }
    )
    return result


def evidence_plan(args: argparse.Namespace) -> dict[str, object]:
    capture = Path(args.capture).expanduser().resolve()
    output = Path(args.out_dir).expanduser().resolve()
    qrenderdoc = first_path("qrenderdoc") or exe_name("qrenderdoc")
    exporter = Path(__file__).with_name("renderdoc_capture_export.py").resolve()
    launch_command = [qrenderdoc]
    batch_candidate = [qrenderdoc, "--python", str(exporter)]
    environment = {
        "RENDERDOC_EXPORT_CAPTURE": str(capture),
        "RENDERDOC_EXPORT_OUT_DIR": str(output),
        "RENDERDOC_EXPORT_EVENTS": args.events,
    }
    powershell = [
        "$env:%s='%s'" % (name, value.replace("'", "''"))
        for name, value in environment.items()
    ]
    powershell.append("& " + command_line(launch_command))
    return {
        "risk": "review-writes-large-proprietary-output",
        "capture": {"path": str(capture), "exists": capture.is_file(), "bytes": capture.stat().st_size if capture.is_file() else None},
        "events": [int(value.strip()) for value in args.events.split(",") if value.strip()],
        "outputDirectory": str(output),
        "environment": environment,
        "script": str(exporter),
        "launchPowerShell": powershell,
        "manualSteps": [
            "Launch qrenderdoc with the process-scoped environment above.",
            "Open Tools > Python Shell.",
            "Load renderdoc_capture_export.py and run it.",
            "Require export_status.json state=complete and exact_export_manifest.json before continuing.",
        ],
        "batchCandidate": {
            "argv": batch_candidate,
            "powershell": command_line(batch_candidate),
            "status": "verify-per-qrenderdoc-build",
            "boundary": "The current local qrenderdoc 1.44 build opened its UI without executing the startup script in smoke tests.",
        },
        "expected": [
            "export_status.json",
            "exact_export_manifest.json",
            "eid_<event>/exact_state.json",
            "resources/textures/*.dds and *.raw",
            "resources/buffers/*.bin",
            "eid_<event>/shaders/* binary and disassembly files",
        ],
        "next": "Review command-risk.md, run the script in qrenderdoc Python Shell, then run renderdoc_evidence_report.py.",
    }


def mcp_config(args: argparse.Namespace) -> dict[str, object]:
    server = first_path("server") or exe_name("renderdoc-mcp")
    if args.client == "codex":
        snippet: dict[str, object] = {
            "toml": ["[mcp_servers.renderdoc-mcp]", f"command = '{server}'", "args = []"]
        }
    else:
        snippet = {"json": {"mcpServers": {"renderdoc-mcp": {"command": server, "args": []}}}}
    return {"client": args.client, "server": server, "config": snippet}


def print_result(data: dict[str, object]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    release = sub.add_parser("release", help="Show primary upstream release metadata")
    release.add_argument("--tag", default="latest")
    sub.add_parser("sources", help="Compare primary and reference upstream metadata")
    sub.add_parser("discover", help="Find server, CLI, qrenderdoc, and replay runtime")

    install = sub.add_parser("install-release", help="Install a verified primary release archive")
    install.add_argument("--tag", default="latest")
    install.add_argument("--asset")
    install.add_argument("--install-dir")
    install.add_argument("--force", action="store_true")

    config = sub.add_parser("mcp-config", help="Generate MCP client configuration")
    config.add_argument("--client", choices=["codex", "claude"], default="codex")

    plan_parser = sub.add_parser("plan", help="Plan a server or CLI command")
    group = plan_parser.add_mutually_exclusive_group()
    group.add_argument("--server", action="store_true")
    group.add_argument("--cli", action="store_true")
    plan_parser.set_defaults(cli=True)
    plan_parser.add_argument("renderdoc_args", nargs=argparse.REMAINDER)

    doctor_parser = sub.add_parser("doctor", help="Diagnose files and optional concrete-capture replay")
    doctor_parser.add_argument("--capture")
    doctor_parser.add_argument("--timeout", type=int, default=120)

    evidence = sub.add_parser("evidence-plan", help="Plan a qrenderdoc exact-evidence export")
    evidence.add_argument("--capture", required=True)
    evidence.add_argument("--events", required=True, help="Comma-separated current-capture event IDs")
    evidence.add_argument("--out-dir", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "release":
        print_result(slim_release(PRIMARY_REPO, args.tag))
    elif args.cmd == "sources":
        print_result({"primary": repo_metadata(PRIMARY_REPO), "reference": repo_metadata(REFERENCE_REPO)})
    elif args.cmd == "discover":
        print_result(discover())
    elif args.cmd == "install-release":
        print_result(install_release(args))
    elif args.cmd == "mcp-config":
        print_result(mcp_config(args))
    elif args.cmd == "plan":
        parts = args.renderdoc_args[1:] if args.renderdoc_args and args.renderdoc_args[0] == "--" else args.renderdoc_args
        print_result(plan(args, parts))
    elif args.cmd == "doctor":
        print_result(doctor(args))
    elif args.cmd == "evidence-plan":
        print_result(evidence_plan(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
