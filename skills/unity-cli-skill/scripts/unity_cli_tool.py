#!/usr/bin/env python3
"""Install/update unity-cli and plan thin Unity Editor automation commands."""

from __future__ import annotations

import argparse
import hashlib
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


REPO = "akiojin/unity-cli"
GITHUB_API = f"https://api.github.com/repos/{REPO}"
RAW_BASE = "https://raw.githubusercontent.com/akiojin/unity-cli"
UPSTREAM_SKILLS_PATH = ".claude-plugin/plugins/unity-cli/skills"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_install_dir() -> Path:
    return repo_root() / "vendor-tools" / "unity-cli" / "bin"


def default_skills_target() -> Path:
    return repo_root() / "targets" / "unity-cli" / "upstream-skills"


def is_windows() -> bool:
    return os.name == "nt"


def platform_key() -> str:
    override = os.environ.get("UNITY_CLI_PLATFORM")
    if override:
        return override
    if is_windows():
        return "win-x64"
    if sys.platform == "darwin":
        return "osx-arm64" if os.uname().machine == "arm64" else "osx-arm64"
    machine = os.uname().machine if hasattr(os, "uname") else ""
    return "linux-arm64" if machine in {"aarch64", "arm64"} else "linux-x64"


def binary_name() -> str:
    return "unity-cli.exe" if is_windows() else "unity-cli"


def http_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": "ai-skill-lab-unity-cli-skill"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def download_file(url: str, output: Path) -> None:
    request = Request(url, headers={"User-Agent": "ai-skill-lab-unity-cli-skill"})
    output.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(request, timeout=120) as response, output.open("wb") as stream:
        shutil.copyfileobj(response, stream)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_release() -> dict[str, object]:
    release = http_json(f"{GITHUB_API}/releases/latest")
    manifest_asset = None
    for asset in release.get("assets", []):  # type: ignore[union-attr]
        if asset.get("name") == "unity-cli-manifest.json":
            manifest_asset = asset
            break
    manifest = None
    if manifest_asset:
        manifest = http_json(str(manifest_asset["browser_download_url"]))
    return {"release": release, "manifest": manifest}


def release_for_tag(tag: str | None) -> dict[str, object]:
    if not tag or tag == "latest":
        return latest_release()
    release = http_json(f"{GITHUB_API}/releases/tags/{tag}")
    manifest_url = f"https://github.com/{REPO}/releases/download/{tag}/unity-cli-manifest.json"
    return {"release": release, "manifest": http_json(manifest_url)}


def dedupe(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path).lower() if is_windows() else str(path)
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def candidate_paths() -> list[Path]:
    paths: list[Path] = []
    env_path = os.environ.get("UNITY_CLI_PATH")
    if env_path:
        paths.append(Path(env_path))
    paths.append(default_install_dir() / binary_name())
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if part:
            paths.append(Path(part) / binary_name())
    return dedupe(paths)


def discover() -> dict[str, object]:
    candidates = candidate_paths()
    matches = [str(path) for path in candidates if path.is_file()]
    return {
        "platform_key": platform_key(),
        "candidates": [str(path) for path in candidates],
        "found": bool(matches),
        "paths": matches,
    }


def first_cli() -> str | None:
    data = discover()
    paths = data["paths"]  # type: ignore[index]
    return paths[0] if paths else None


def command_line(args: list[str]) -> str:
    return subprocess.list2cmdline(args)


def run_command(args: list[str], timeout: float = 30.0) -> dict[str, object]:
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    return {
        "argv": args,
        "powershell": command_line(args),
        "returncode": completed.returncode,
        "stdout": completed.stdout.splitlines(),
        "stderr": completed.stderr.splitlines(),
    }


def version() -> dict[str, object]:
    cli = first_cli()
    if not cli:
        return {"error": "unity-cli was not found", "discover": discover()}
    return run_command([cli, "--version"])


def update_cli(args: argparse.Namespace) -> dict[str, object]:
    data = release_for_tag(args.tag)
    release = data["release"]  # type: ignore[assignment]
    manifest = data["manifest"]  # type: ignore[assignment]
    key = args.platform or platform_key()
    assets = manifest.get("assets", {}) if isinstance(manifest, dict) else {}
    asset = assets.get(key) if isinstance(assets, dict) else None
    if not isinstance(asset, dict):
        raise ValueError(f"platform asset not found in manifest: {key}")

    install_dir = Path(args.install_dir).resolve() if args.install_dir else default_install_dir()
    output = install_dir / binary_name()

    with tempfile.TemporaryDirectory(prefix="unity-cli-download-") as tmp:
        temp_file = Path(tmp) / f"unity-cli-{key}"
        download_file(str(asset["url"]), temp_file)
        actual_sha = sha256_file(temp_file)
        expected_sha = str(asset.get("sha256", "")).lower()
        if expected_sha and actual_sha.lower() != expected_sha:
            raise ValueError(f"sha256 mismatch: expected {expected_sha}, got {actual_sha}")

        install_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(temp_file, output)
        if not is_windows():
            mode = output.stat().st_mode
            output.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    metadata = {
        "repo": REPO,
        "tag": release.get("tag_name") if isinstance(release, dict) else args.tag,
        "published_at": release.get("published_at") if isinstance(release, dict) else None,
        "platform": key,
        "asset_url": asset["url"],
        "sha256": actual_sha,
        "installed_path": str(output),
    }
    (install_dir.parent / "VERSION.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"installed": metadata, "version": run_command([str(output), "--version"])}


def sync_skills(args: argparse.Namespace) -> dict[str, object]:
    data = release_for_tag(args.tag)
    release = data["release"]  # type: ignore[assignment]
    tag = str(release.get("tag_name") if isinstance(release, dict) else args.tag)
    archive_url = f"https://github.com/{REPO}/archive/refs/tags/{tag}.zip"
    target = Path(args.target).resolve() if args.target else default_skills_target()

    with tempfile.TemporaryDirectory(prefix="unity-cli-source-") as tmp:
        archive = Path(tmp) / f"{tag}.zip"
        extract_dir = Path(tmp) / "extract"
        download_file(archive_url, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(extract_dir)
        roots = [path for path in extract_dir.iterdir() if path.is_dir()]
        if not roots:
            raise FileNotFoundError("source archive root was not found")
        source = roots[0] / UPSTREAM_SKILLS_PATH
        if not source.is_dir():
            raise FileNotFoundError(f"upstream skills path was not found: {UPSTREAM_SKILLS_PATH}")

        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)

    metadata = {
        "repo": REPO,
        "tag": tag,
        "source_path": UPSTREAM_SKILLS_PATH,
        "target": str(target),
        "archive_url": archive_url,
    }
    (target.parent / "SOURCE.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"synced": metadata, "skills": sorted(path.name for path in target.iterdir() if path.is_dir())}


def risk_for_command(parts: list[str], dry_run: bool) -> str:
    if not parts:
        return "unknown"
    root = parts[0]
    if root in {"--version", "help"}:
        return "low"
    if root == "cli" and len(parts) > 1 and parts[1] in {"doctor"}:
        return "low"
    if root == "system" and len(parts) > 1 and parts[1] == "ping":
        return "low"
    if root == "instances" and len(parts) > 1 and parts[1] == "list":
        return "low"
    if root == "tool" and len(parts) > 1 and parts[1] in {"list", "schema"}:
        return "low"
    if root == "skills" and len(parts) > 1 and parts[1] == "lint":
        return "low"
    if dry_run:
        return "planned-dry-run"
    if root in {"scene", "tool", "batch", "raw"}:
        return "state-changing-or-high-risk"
    if root == "cli" and len(parts) > 1 and parts[1] == "install":
        return "state-changing"
    return "review"


def plan(args: argparse.Namespace, command_parts: list[str]) -> dict[str, object]:
    cli = first_cli() or binary_name()
    command = [cli]
    if args.output_json and "--output" not in command_parts:
        command.extend(["--output", "json"])
    if args.dry_run and "--dry-run" not in command_parts:
        command.append("--dry-run")
    command.extend(command_parts)
    return {
        "risk": risk_for_command(command_parts, args.dry_run),
        "argv": command,
        "powershell": command_line(command),
        "notes": [
            "Prefer low-risk health checks before Editor writes.",
            "Inspect JSON payloads before tool call or batch execution.",
        ],
        "discover": discover(),
    }


def print_result(data: dict[str, object]) -> None:
    print(json.dumps(data, indent=2))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("release", help="Show latest upstream release and manifest")
    sub.add_parser("discover", help="Find local unity-cli binaries")
    sub.add_parser("version", help="Run unity-cli --version")

    update = sub.add_parser("update-cli", help="Download or update unity-cli from GitHub Releases")
    update.add_argument("--tag", default="latest")
    update.add_argument("--platform")
    update.add_argument("--install-dir")

    sync = sub.add_parser("sync-skills", help="Sync upstream workflow skills from the release source archive")
    sync.add_argument("--tag", default="latest")
    sync.add_argument("--target")

    plan_parser = sub.add_parser("plan", help="Plan a unity-cli command")
    plan_parser.add_argument("--dry-run", action="store_true")
    plan_parser.add_argument("--no-output-json", dest="output_json", action="store_false")
    plan_parser.set_defaults(output_json=True)
    plan_parser.add_argument("unity_args", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)

    if args.cmd == "release":
        print_result(latest_release())
    elif args.cmd == "discover":
        print_result(discover())
    elif args.cmd == "version":
        print_result(version())
    elif args.cmd == "update-cli":
        print_result(update_cli(args))
    elif args.cmd == "sync-skills":
        print_result(sync_skills(args))
    elif args.cmd == "plan":
        parts = args.unity_args
        if parts and parts[0] == "--":
            parts = parts[1:]
        print_result(plan(args, parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
