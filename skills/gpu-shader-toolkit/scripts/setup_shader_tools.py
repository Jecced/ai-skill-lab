#!/usr/bin/env python3
"""Install or register local shader-analysis tools for gpu-shader-toolkit."""

from __future__ import annotations

import argparse
import glob
import json
import platform
import re
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
REPO_ROOT = SKILL_DIR.parents[1]
TOOLS_DIR = REPO_ROOT / "vendor-tools" / "gpu-shader-toolkit"
MANIFEST_PATH = SCRIPT_DIR / "tool_manifest.json"
LOCAL_TOOLCHAIN_PATH = TOOLS_DIR / "toolchain.local.json"


def platform_id() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
    if system == "windows":
        return f"win-{arch}"
    if system == "darwin":
        return f"macos-{arch}"
    if system == "linux":
        return f"linux-{arch}"
    return f"{system}-{arch}"


def load_manifest() -> dict:
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_local_toolchain() -> dict:
    if not LOCAL_TOOLCHAIN_PATH.exists():
        return {"schema": 1, "tools": {}}
    with LOCAL_TOOLCHAIN_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_local_toolchain(data: dict) -> None:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    with LOCAL_TOOLCHAIN_PATH.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def github_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "codex-gpu-shader-toolkit"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "codex-gpu-shader-toolkit"})
    with urllib.request.urlopen(req, timeout=120) as response, destination.open("wb") as f:
        shutil.copyfileobj(response, f)


def extract_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    suffixes = "".join(archive.suffixes).lower()
    if suffixes.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(destination)
    elif suffixes.endswith(".tar.gz") or suffixes.endswith(".tgz"):
        with tarfile.open(archive, "r:gz") as t:
            t.extractall(destination)
    else:
        raise ValueError(f"Unsupported archive type: {archive}")


def find_tool(manifest: dict, tool_id: str) -> dict:
    for tool in manifest["tools"]:
        if tool["id"] == tool_id:
            return tool
    raise SystemExit(f"Unknown tool id: {tool_id}")


def command_name(command: str) -> str:
    return command + ".exe" if platform.system().lower() == "windows" and not command.endswith(".exe") else command


def first_existing_command(root: Path, commands: list[str], plat: str | None = None) -> Path | None:
    names = [command_name(c) for c in commands]
    preferred_parts: list[str] = []
    if plat == "win-x64":
        preferred_parts = ["/bin/x64/", "\\bin\\x64\\"]
    elif plat == "win-arm64":
        preferred_parts = ["/bin/arm64/", "\\bin\\arm64\\"]
    elif plat == "win-x86":
        preferred_parts = ["/bin/x86/", "\\bin\\x86\\"]

    for name in names:
        hits = list(root.rglob(name))
        for hit in hits:
            normalized = str(hit).replace("\\", "/").lower()
            if any(part.replace("\\", "/") in normalized for part in preferred_parts):
                return hit
        if hits:
            return hits[0]
    return None


def prune_windows_dxc_runtime(destination: Path, cmd_path: Path) -> Path:
    """Keep only the runtime files needed to invoke dxc on Windows."""
    minimal_dir = destination / "runtime-x64"
    source_dir = cmd_path.parent
    keep = ["dxc.exe", "dxcompiler.dll", "dxil.dll"]
    staged = {}
    for name in keep:
        src = source_dir / name
        if not src.exists():
            raise SystemExit(f"DXC runtime file is missing: {src}")
        staged[name] = src.read_bytes()

    for child in destination.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    minimal_dir.mkdir(parents=True, exist_ok=True)
    for name, data in staged.items():
        (minimal_dir / name).write_bytes(data)
    return minimal_dir / "dxc.exe"


def register_tool(tool_id: str, command: str, path: Path, source: str) -> None:
    data = load_local_toolchain()
    data.setdefault("tools", {})[tool_id] = {
        "command": command,
        "path": str(path),
        "source": source,
        "platform": platform_id(),
    }
    save_local_toolchain(data)


def install_github_release(tool: dict, plat: str, force: bool) -> None:
    release_source = None
    for source in tool.get("sources", []):
        if source.get("type") == "github_release":
            release_source = source
            break
    if not release_source:
        raise SystemExit(f"{tool['id']} has no github_release source in manifest.")

    pattern = release_source.get("asset_patterns", {}).get(plat)
    if not pattern:
        raise SystemExit(f"No release asset pattern for {tool['id']} on {plat}.")

    release = github_json(release_source["latest_release_api"])
    assets = release.get("assets", [])
    selected = None
    rx = re.compile(pattern)
    for asset in assets:
        if rx.search(asset.get("name", "")):
            selected = asset
            break
    if not selected:
        names = ", ".join(a.get("name", "") for a in assets)
        raise SystemExit(f"No asset matched {pattern}. Available assets: {names}")

    tag = release.get("tag_name") or "unknown"
    archive = TOOLS_DIR / "downloads" / selected["name"]
    destination = TOOLS_DIR / plat / tool["id"] / tag
    if destination.exists() and not force:
        cmd_path = first_existing_command(destination, tool["commands"], plat)
        if cmd_path:
            register_tool(tool["id"], tool["commands"][0], cmd_path, release.get("html_url", ""))
            print(f"Already installed: {cmd_path}")
            return

    print(f"Downloading {selected['browser_download_url']}")
    download(selected["browser_download_url"], archive)
    extract_archive(archive, destination)
    cmd_path = first_existing_command(destination, tool["commands"], plat)
    if not cmd_path:
        raise SystemExit(f"Installed {tool['id']} but could not find commands {tool['commands']} under {destination}")
    if tool["id"] == "dxc" and plat == "win-x64":
        cmd_path = prune_windows_dxc_runtime(destination, cmd_path)
    register_tool(tool["id"], tool["commands"][0], cmd_path, release.get("html_url", ""))
    archive.unlink(missing_ok=True)
    print(f"Registered {tool['id']}: {cmd_path}")


def register_windows_sdk_dxc(force: bool) -> None:
    if platform.system().lower() != "windows":
        raise SystemExit("--register-windows-sdk-dxc is only valid on Windows.")

    hits = sorted(
        glob.glob("C:/Program Files (x86)/Windows Kits/10/bin/*/x64/dxc.exe"),
        reverse=True,
    )
    if not hits:
        raise SystemExit("No Windows SDK dxc.exe found.")

    src = Path(hits[0])
    version = src.parent.parent.name
    destination = TOOLS_DIR / "win-x64" / "dxc" / f"windows-sdk-{version}"
    destination.mkdir(parents=True, exist_ok=True)
    for name in ["dxc.exe", "dxcompiler.dll", "dxil.dll"]:
        p = src.parent / name
        if p.exists():
            shutil.copy2(p, destination / name)

    cmd_path = destination / "dxc.exe"
    if not cmd_path.exists() and not force:
        raise SystemExit(f"Failed to copy dxc.exe to {destination}")
    register_tool("dxc", "dxc", cmd_path, f"Windows SDK {version}")
    print(f"Registered Windows SDK dxc: {cmd_path}")


def print_hints(manifest: dict, plat: str) -> None:
    print(f"Platform: {plat}")
    for tool in manifest["tools"]:
        print(f"\n[{tool['id']}] {tool.get('purpose', '')}")
        for source in tool.get("sources", []):
            if source.get("homepage"):
                print(f"  source: {source['homepage']}")
            for command in source.get("commands", []):
                print(f"  install: {command}")
        for hint in tool.get("install_hints", {}).get(plat.split("-")[0], []):
            print(f"  note: {hint}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "register-windows-sdk-dxc", "hints"])
    parser.add_argument("--tool", default="dxc", help="Tool id from tool_manifest.json")
    parser.add_argument("--platform", default=platform_id(), help="Target platform id, e.g. win-x64, macos-arm64")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest()
    if args.action == "install":
        install_github_release(find_tool(manifest, args.tool), args.platform, args.force)
    elif args.action == "register-windows-sdk-dxc":
        register_windows_sdk_dxc(args.force)
    elif args.action == "hints":
        print_hints(manifest, args.platform)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
