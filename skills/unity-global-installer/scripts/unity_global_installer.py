#!/usr/bin/env python3
"""Cross-platform Unity Hub module install and repair helper."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterable


CHILD_KEYS = ("children", "childModules", "subModules", "modules")


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d%H%M%S")


def system_name() -> str:
    return platform.system().lower()


def default_editor_roots(extra_root: str | None = None) -> list[Path]:
    roots: list[Path] = []
    for env_name in ("UNITY_EDITOR_ROOT", "UNITY_HUB_EDITOR_ROOT"):
        value = os.environ.get(env_name)
        if value:
            roots.append(Path(value).expanduser())
    if extra_root:
        roots.append(Path(extra_root).expanduser())

    if system_name() == "windows":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            value = os.environ.get(env_name)
            if value:
                roots.append(Path(value) / "Unity" / "Hub" / "Editor")
    elif system_name() == "darwin":
        roots.extend(
            [
                Path("/Applications/Unity/Hub/Editor"),
                Path.home() / "Applications" / "Unity" / "Hub" / "Editor",
            ]
        )
    else:
        roots.extend(
            [
                Path.home() / "Unity" / "Hub" / "Editor",
                Path.home() / ".local" / "share" / "Unity" / "Hub" / "Editor",
                Path("/opt/Unity/Hub/Editor"),
            ]
        )

    seen: set[Path] = set()
    result: list[Path] = []
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            resolved = root
        if resolved not in seen and resolved.exists():
            seen.add(resolved)
            result.append(resolved)
    return result


def unity_executable(editor: Path) -> Path | None:
    candidates: list[Path]
    if system_name() == "windows":
        candidates = [editor / "Editor" / "Unity.com", editor / "Editor" / "Unity.exe"]
    elif system_name() == "darwin":
        candidates = [
            editor / "Unity.app" / "Contents" / "MacOS" / "Unity",
            editor / "Editor" / "Unity",
        ]
    else:
        candidates = [editor / "Editor" / "Unity", editor / "Unity"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def discover_editors(editor_root: str | None = None) -> list[dict[str, Any]]:
    editors: list[dict[str, Any]] = []
    for root in default_editor_roots(editor_root):
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            exe = unity_executable(child)
            modules = child / "modules.json"
            if exe:
                editors.append(
                    {
                        "version": child.name,
                        "path": str(child),
                        "unity": str(exe),
                        "modules_json": str(modules) if modules.exists() else None,
                    }
                )
    return editors


def resolve_editor(args: argparse.Namespace) -> Path:
    if args.editor_path:
        editor = Path(args.editor_path).expanduser().resolve()
        if not editor.exists():
            raise SystemExit(f"Editor path does not exist: {editor}")
        if not unity_executable(editor):
            raise SystemExit(f"Path is not a Unity Editor install: {editor}")
        return editor

    if not args.editor_version:
        raise SystemExit("Provide --editor-version or --editor-path.")

    matches = [e for e in discover_editors(args.editor_root) if e["version"] == args.editor_version]
    if len(matches) != 1:
        raise SystemExit(f"Expected one editor version {args.editor_version!r}, found {len(matches)}.")
    return Path(matches[0]["path"])


def modules_json_path(editor: Path) -> Path:
    path = editor / "modules.json"
    if not path.exists():
        raise SystemExit(f"Missing modules.json: {path}")
    return path


def load_modules(editor: Path) -> list[dict[str, Any]]:
    with modules_json_path(editor).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected modules.json shape: {modules_json_path(editor)}")
    return data


def iter_modules(
    entries: Iterable[dict[str, Any]],
    parent: str | None = None,
    seen: set[str] | None = None,
) -> Iterable[dict[str, Any]]:
    if seen is None:
        seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id") or "")
        if entry_id and entry_id not in seen:
            item = dict(entry)
            item["_parent"] = parent or entry.get("parent") or None
            yield item
            seen.add(entry_id)
        for key in CHILD_KEYS:
            children = entry.get(key)
            if isinstance(children, list):
                yield from iter_modules(children, parent=entry_id or parent, seen=seen)


def find_modules(editor: Path, module_id: str, include_children: bool = False) -> list[dict[str, Any]]:
    all_modules = list(iter_modules(load_modules(editor)))
    matches = [m for m in all_modules if m.get("id") == module_id]
    if not matches:
        raise SystemExit(f"Module id not found in {modules_json_path(editor)}: {module_id}")
    if len(matches) > 1:
        raise SystemExit(f"Module id is ambiguous in {modules_json_path(editor)}: {module_id}")
    if not include_children:
        return matches

    wanted = {module_id}
    changed = True
    while changed:
        changed = False
        for module in all_modules:
            if module.get("_parent") in wanted and module.get("id") not in wanted:
                wanted.add(str(module.get("id")))
                changed = True
    return [m for m in all_modules if m.get("id") in wanted]


def module_url(module: dict[str, Any]) -> str | None:
    value = module.get("downloadUrl") or module.get("url")
    return str(value) if value else None


def module_destination(editor: Path, module: dict[str, Any]) -> Path | None:
    destination = module.get("destination")
    if not destination:
        return None
    return expand_unity_path(editor, str(destination))


def expand_unity_path(editor: Path, value: str) -> Path:
    return Path(value.replace("{UNITY_PATH}", str(editor))).expanduser()


def module_final_path(editor: Path, module: dict[str, Any]) -> Path | None:
    rename_to = module.get("renameTo")
    if rename_to:
        return expand_unity_path(editor, str(rename_to))
    extracted = module.get("extractedPathRename")
    if isinstance(extracted, dict) and extracted.get("to"):
        return expand_unity_path(editor, str(extracted["to"]))
    return module_destination(editor, module)


def format_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        return
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    print("  ".join(column.ljust(widths[column]) for column in columns))
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


def proxy_opener(proxy: str | None, follow_redirects: bool = True) -> urllib.request.OpenerDirector:
    handlers: list[Any] = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    if not follow_redirects:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
                return None

        handlers.append(NoRedirect)
    return urllib.request.build_opener(*handlers)


def test_url(url: str, proxy: str | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "unity-global-installer/1.0"})
    opener = proxy_opener(proxy, follow_redirects=False)
    try:
        with opener.open(request, timeout=30) as response:
            return {
                "url": url,
                "status": response.status,
                "location": response.headers.get("Location", ""),
                "content_length": response.headers.get("Content-Length", ""),
                "proxy": proxy or "",
                "china_redirect": "download.unitychina.cn" in response.headers.get("Location", ""),
            }
    except urllib.error.HTTPError as exc:
        return {
            "url": url,
            "status": exc.code,
            "location": exc.headers.get("Location", ""),
            "content_length": exc.headers.get("Content-Length", ""),
            "proxy": proxy or "",
            "china_redirect": "download.unitychina.cn" in exc.headers.get("Location", ""),
        }
    except urllib.error.URLError as exc:
        return {
            "url": url,
            "status": "network-error",
            "error": str(exc.reason),
            "location": "",
            "content_length": "",
            "proxy": proxy or "",
            "china_redirect": False,
        }


def download_url(url: str, out_dir: Path, proxy: str | None = None) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    name = Path(urllib.parse.urlparse(url).path).name
    if not name:
        raise SystemExit(f"URL has no file name: {url}")
    target = out_dir / name
    request = urllib.request.Request(url, headers={"User-Agent": "unity-global-installer/1.0"})
    opener = proxy_opener(proxy, follow_redirects=True)
    sha = hashlib.sha256()
    with opener.open(request, timeout=60) as response, target.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            sha.update(chunk)
    return {"path": str(target), "bytes": target.stat().st_size, "sha256": sha.hexdigest()}


def safe_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def run_command(command: list[str], apply: bool, cwd: Path | None = None) -> int:
    print("COMMAND:", " ".join(command))
    if not apply:
        print("dry-run: add --apply to execute")
        return 0
    return subprocess.run(command, cwd=str(cwd) if cwd else None, check=False).returncode


def install_archive(installer: Path, destination: Path, apply: bool, strip_single_root: bool) -> None:
    print(f"archive: {installer}")
    print(f"destination: {destination}")
    if not safe_under(destination, destination.anchor and Path(destination.anchor) or destination):
        raise SystemExit(f"Refusing suspicious destination: {destination}")
    if not apply:
        print("dry-run: add --apply to extract")
        return
    destination.mkdir(parents=True, exist_ok=True)
    if installer.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory(prefix="unity-module-zip-") as temp_name:
            temp = Path(temp_name)
            with zipfile.ZipFile(installer) as archive:
                archive.extractall(temp)
            roots = [p for p in temp.iterdir()]
            source = roots[0] if strip_single_root and len(roots) == 1 and roots[0].is_dir() else temp
            for child in source.iterdir():
                target = destination / child.name
                if child.is_dir():
                    shutil.copytree(child, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(child, target)
    else:
        raise SystemExit(f"Archive install is only implemented for .zip: {installer}")


def install_module(args: argparse.Namespace) -> None:
    editor = resolve_editor(args)
    modules = find_modules(editor, args.module_id, include_children=False)
    module = modules[0]
    installer = Path(args.installer).expanduser().resolve() if args.installer else None
    if not installer:
        url = module_url(module)
        if not url:
            raise SystemExit(f"Module has no download URL: {args.module_id}")
        result = download_url(url, Path(args.out_dir).expanduser(), args.proxy)
        installer = Path(result["path"])
        print(json.dumps(result, indent=2))

    suffixes = "".join(installer.suffixes).lower()
    if system_name() == "windows" and installer.suffix.lower() == ".exe":
        code = run_command([str(installer), "/S", f"/D={editor}"], args.apply)
    elif system_name() == "darwin" and installer.suffix.lower() == ".pkg":
        code = run_command(["sudo", "installer", "-pkg", str(installer), "-target", "/"], args.apply)
    elif suffixes.endswith(".zip"):
        destination = module_destination(editor, module)
        if not destination:
            raise SystemExit(f"Module has no destination for archive extraction: {args.module_id}")
        if not safe_under(destination, editor):
            raise SystemExit(f"Refusing archive extraction outside editor root: {destination}")
        install_archive(installer, destination, args.apply, args.strip_single_root)
        code = 0
    else:
        print(f"No generic installer handler for {installer.name} on {system_name()}.")
        print("Use the printed installer path and Unity module metadata to run a platform-specific installer.")
        code = 2
    if code != 0:
        raise SystemExit(code)


def set_selected_recursive(entry: dict[str, Any], wanted: set[str]) -> None:
    if entry.get("id") in wanted:
        entry["selected"] = True
    for key in CHILD_KEYS:
        children = entry.get(key)
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    set_selected_recursive(child, wanted)


def mark_selected(args: argparse.Namespace) -> None:
    editor = resolve_editor(args)
    targets = {m["id"] for m in find_modules(editor, args.module_id, include_children=args.include_children)}
    path = modules_json_path(editor)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    for entry in data:
        if isinstance(entry, dict):
            set_selected_recursive(entry, targets)
    backup = path.with_name(path.name + f".bak-unity-global-installer-{now_stamp()}")
    print(f"modules.json: {path}")
    print(f"backup: {backup}")
    print(f"marked: {', '.join(sorted(targets))}")
    if not args.apply:
        print("dry-run: add --apply to write modules.json")
        return
    shutil.copy2(path, backup)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def compare_modules(args: argparse.Namespace) -> None:
    editor = resolve_editor(args)
    donor_args = argparse.Namespace(**vars(args))
    donor_args.editor_path = args.donor_editor_path
    donor_args.editor_version = args.donor_editor_version
    donor = resolve_editor(donor_args)
    target_modules = {m.get("id"): m for m in find_modules(editor, args.module_id, args.include_children)}
    donor_modules = {m.get("id"): m for m in find_modules(donor, args.module_id, args.include_children)}
    rows: list[dict[str, Any]] = []
    for module_id in sorted(set(target_modules) | set(donor_modules)):
        target = target_modules.get(module_id)
        source = donor_modules.get(module_id)
        rows.append(
            {
                "id": module_id,
                "same_url": bool(target and source and module_url(target) == module_url(source)),
                "target_path": module_final_path(editor, target) if target else "",
                "donor_path": module_final_path(donor, source) if source else "",
            }
        )
    format_table(rows, ["id", "same_url", "target_path", "donor_path"])


def copy_module_payloads(args: argparse.Namespace) -> None:
    editor = resolve_editor(args)
    donor_args = argparse.Namespace(**vars(args))
    donor_args.editor_path = args.donor_editor_path
    donor_args.editor_version = args.donor_editor_version
    donor = resolve_editor(donor_args)
    target_modules = {m.get("id"): m for m in find_modules(editor, args.module_id, args.include_children)}
    donor_modules = {m.get("id"): m for m in find_modules(donor, args.module_id, args.include_children)}
    for module_id, target_module in target_modules.items():
        donor_module = donor_modules.get(module_id)
        if not donor_module:
            raise SystemExit(f"Donor editor has no module: {module_id}")
        if module_url(target_module) != module_url(donor_module) and not args.allow_different_url:
            print(f"skip {module_id}: module URL differs")
            continue
        source = module_final_path(donor, donor_module) or module_destination(donor, donor_module)
        target = module_final_path(editor, target_module) or module_destination(editor, target_module)
        if not source or not target:
            print(f"skip {module_id}: missing destination metadata")
            continue
        if not source.exists():
            print(f"skip {module_id}: source missing: {source}")
            continue
        if not safe_under(source, donor) or not safe_under(target, editor):
            raise SystemExit(f"Refusing copy outside editor roots: {module_id}")
        print(f"copy {module_id}: {source} -> {target}")
        if args.apply:
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    if not args.apply:
        print("dry-run: add --apply to copy payloads")


def create_temp_project(unity: Path) -> Path:
    project = Path(tempfile.gettempdir()) / f"UnityModuleCheck_{now_stamp()}"
    log = Path(tempfile.gettempdir()) / f"unity-create-project-{now_stamp()}.log"
    command = [str(unity), "-batchmode", "-nographics", "-quit", "-createProject", str(project), "-logFile", str(log)]
    code = subprocess.run(command, check=False).returncode
    if code != 0:
        raise SystemExit(f"Unity createProject failed with exit code {code}. Log: {log}")
    return project


def validate_build_target(args: argparse.Namespace) -> None:
    editor = resolve_editor(args)
    unity = unity_executable(editor)
    if not unity:
        raise SystemExit(f"Unity executable not found: {editor}")
    if not args.build_target:
        raise SystemExit("Provide --build-target, for example Android, iOS, WebGL, StandaloneOSX, StandaloneLinux64.")

    project = Path(args.project_path).expanduser().resolve() if args.project_path else create_temp_project(unity)
    log = Path(tempfile.gettempdir()) / f"unity-validate-{args.build_target}-{now_stamp()}.log"
    command = [
        str(unity),
        "-batchmode",
        "-nographics",
        "-quit",
        "-projectPath",
        str(project),
        "-buildTarget",
        args.build_target,
        "-logFile",
        str(log),
    ]
    command.extend(args.unity_arg or [])
    code = subprocess.run(command, check=False).returncode
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    ok = code == 0 and f"Targeting platform: {args.build_target}" in text
    failed = "Could not add platformSupportModule" in text or "VTable setup" in text
    print(json.dumps({"exit_code": code, "log": str(log), "project": str(project), "loaded": ok, "module_failure": failed}, indent=2))
    if not args.keep_project and not args.project_path and safe_under(project, Path(tempfile.gettempdir())):
        shutil.rmtree(project, ignore_errors=True)
    if not ok or failed:
        raise SystemExit("Unity build target validation failed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Unity Hub module install/repair helper")
    parser.add_argument("action", choices=[
        "list-editors",
        "list-modules",
        "inspect-module",
        "test-url",
        "download-module",
        "install-module",
        "mark-selected",
        "compare-modules",
        "copy-module-payloads",
        "validate-build-target",
    ])
    parser.add_argument("--editor-version")
    parser.add_argument("--editor-path")
    parser.add_argument("--editor-root")
    parser.add_argument("--donor-editor-version")
    parser.add_argument("--donor-editor-path")
    parser.add_argument("--module-id")
    parser.add_argument("--include-children", action="store_true")
    parser.add_argument("--proxy")
    parser.add_argument("--out-dir", default=str(Path.home() / "Downloads"))
    parser.add_argument("--installer")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--strip-single-root", action="store_true")
    parser.add_argument("--allow-different-url", action="store_true")
    parser.add_argument("--build-target")
    parser.add_argument("--project-path")
    parser.add_argument("--keep-project", action="store_true")
    parser.add_argument("--unity-arg", action="append")
    args = parser.parse_args()

    if args.action == "list-editors":
        format_table(discover_editors(args.editor_root), ["version", "path", "unity", "modules_json"])
        return 0

    if args.action == "list-modules":
        editor = resolve_editor(args)
        modules = list(iter_modules(load_modules(editor)))
        if args.module_id:
            needle = args.module_id.lower()
            modules = [m for m in modules if needle in str(m.get("id", "")).lower()]
        rows = [
            {
                "id": m.get("id", ""),
                "parent": m.get("_parent") or "",
                "selected": m.get("selected", ""),
                "destination": module_destination(editor, m) or "",
                "url": module_url(m) or "",
            }
            for m in modules
        ]
        format_table(rows, ["id", "parent", "selected", "destination", "url"])
        return 0

    if args.action in {"inspect-module", "test-url", "download-module", "install-module", "mark-selected", "compare-modules", "copy-module-payloads"} and not args.module_id:
        raise SystemExit("Provide --module-id.")

    if args.action == "inspect-module":
        editor = resolve_editor(args)
        rows = []
        for module in find_modules(editor, args.module_id, args.include_children):
            destination = module_destination(editor, module)
            final_path = module_final_path(editor, module)
            check_path = final_path or destination
            rows.append(
                {
                    "id": module.get("id", ""),
                    "selected": module.get("selected", ""),
                    "destination": destination or "",
                    "final_path": final_path or "",
                    "exists": check_path.exists() if check_path else "",
                    "url": module_url(module) or "",
                }
            )
        format_table(rows, ["id", "selected", "exists", "destination", "final_path", "url"])
        return 0

    if args.action == "test-url":
        editor = resolve_editor(args)
        for module in find_modules(editor, args.module_id, args.include_children):
            url = module_url(module)
            if url:
                print(json.dumps({"id": module.get("id"), **test_url(url, args.proxy)}, indent=2))
        return 0

    if args.action == "download-module":
        editor = resolve_editor(args)
        for module in find_modules(editor, args.module_id, args.include_children):
            url = module_url(module)
            if url:
                result = download_url(url, Path(args.out_dir).expanduser(), args.proxy)
                print(json.dumps({"id": module.get("id"), **result}, indent=2))
        return 0

    if args.action == "install-module":
        install_module(args)
        return 0

    if args.action == "mark-selected":
        mark_selected(args)
        return 0

    if args.action == "compare-modules":
        if not (args.donor_editor_path or args.donor_editor_version):
            raise SystemExit("Provide --donor-editor-path or --donor-editor-version.")
        compare_modules(args)
        return 0

    if args.action == "copy-module-payloads":
        if not (args.donor_editor_path or args.donor_editor_version):
            raise SystemExit("Provide --donor-editor-path or --donor-editor-version.")
        copy_module_payloads(args)
        return 0

    if args.action == "validate-build-target":
        validate_build_target(args)
        return 0

    raise SystemExit(f"Unhandled action: {args.action}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        eprint("interrupted")
        raise SystemExit(130)
