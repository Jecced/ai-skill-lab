from __future__ import annotations

import argparse
import ctypes
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pix_cpp_export_index import (
    ensure_required_files,
    parse_frame_call_order,
    parse_reader_sizes_by_function,
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def human_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(value)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{value} B"


class XpressDecompressor:
    """Small wrapper around the Windows Cabinet XPRESS decompressor."""

    def __init__(self) -> None:
        if not hasattr(ctypes, "WinDLL"):
            raise RuntimeError("PIX resources.bin XPRESS extraction requires Windows.")

        self._cabinet = ctypes.WinDLL("Cabinet")
        self._cabinet.CreateDecompressor.argtypes = [
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._cabinet.CreateDecompressor.restype = ctypes.c_int
        self._cabinet.Decompress.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self._cabinet.Decompress.restype = ctypes.c_int
        self._cabinet.CloseDecompressor.argtypes = [ctypes.c_void_p]
        self._handle = ctypes.c_void_p()
        if not self._cabinet.CreateDecompressor(3, None, ctypes.byref(self._handle)):
            raise ctypes.WinError()

    def close(self) -> None:
        if self._handle:
            self._cabinet.CloseDecompressor(self._handle)
            self._handle = ctypes.c_void_p()

    def decompress(self, compressed: bytes) -> bytes:
        source = ctypes.create_string_buffer(compressed, len(compressed))
        required = ctypes.c_size_t()
        self._cabinet.Decompress(
            self._handle, source, len(compressed), None, 0, ctypes.byref(required)
        )
        destination = ctypes.create_string_buffer(required.value)
        written = ctypes.c_size_t()
        if not self._cabinet.Decompress(
            self._handle,
            source,
            len(compressed),
            destination,
            required.value,
            ctypes.byref(written),
        ):
            raise ctypes.WinError()
        return destination.raw[: written.value]

    def __enter__(self) -> "XpressDecompressor":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def build_stream_offsets(pix_dir: Path) -> dict[str, list[dict[str, int]]]:
    read_sizes_by_function, _ = parse_reader_sizes_by_function(pix_dir)
    call_order = parse_frame_call_order(pix_dir)

    offsets: dict[str, list[dict[str, int]]] = {}
    offset = 0
    for call_index, function_name in enumerate(call_order):
        for read_index, compressed_size in enumerate(
            read_sizes_by_function.get(function_name, [])
        ):
            offsets.setdefault(function_name, []).append(
                {
                    "call_index": call_index,
                    "read_index": read_index,
                    "compressed_offset": offset,
                    "compressed_size": compressed_size,
                }
            )
            offset += compressed_size
    return offsets


def parse_pso_stage_lengths(pix_dir: Path, pso_id: int) -> list[tuple[str, int]]:
    text = read_text(pix_dir / "CreatePSOs.cpp")
    function_re = re.compile(
        rf"void\s+Create(?:Graphics|Compute)PipelineState_{pso_id}\s*\("
    )
    match = function_re.search(text)
    if match is None:
        raise SystemExit(f"CreatePSOs.cpp does not contain PSO {pso_id}.")

    tail = text[match.end() :]
    next_function = re.search(r"\n\s*void\s+Create", tail)
    body = tail[: next_function.start()] if next_function else tail
    stage_re = re.compile(
        r"psoDesc\.(VS|PS|CS|HS|DS|GS)\s*=\s*\{[^,]+,\s*(\d+)\s*\}"
    )
    stages = [(match.group(1), int(match.group(2))) for match in stage_re.finditer(body)]
    if not stages:
        raise SystemExit(f"PSO {pso_id} has no parsed shader stage byte lengths.")
    return stages


def find_pso_function(
    offsets: dict[str, list[dict[str, int]]], pso_id: int
) -> str:
    for prefix in ("CreateGraphicsPipelineState_", "CreateComputePipelineState_"):
        function_name = f"{prefix}{pso_id}"
        if function_name in offsets:
            return function_name
    raise SystemExit(f"The replay read stream does not contain PSO {pso_id}.")


def find_dxc(explicit_path: str | None) -> str | None:
    if explicit_path:
        return explicit_path

    on_path = shutil.which("dxc")
    if on_path:
        return on_path

    windows_kits = Path(r"C:\Program Files (x86)\Windows Kits\10\bin")
    if windows_kits.is_dir():
        candidates = sorted(windows_kits.glob("10.*/x64/dxc.exe"))
        if candidates:
            return str(candidates[-1])

    return None


def read_and_decompress_blocks(
    handle,
    decompressor: XpressDecompressor,
    blocks: list[dict[str, int]],
) -> list[dict[str, Any]]:
    decompressed_blocks: list[dict[str, Any]] = []
    for block in blocks:
        handle.seek(block["compressed_offset"])
        compressed = handle.read(block["compressed_size"])
        decompressed = decompressor.decompress(compressed)
        decompressed_blocks.append(
            {
                **block,
                "decompressed_size": len(decompressed),
                "data": decompressed,
            }
        )
    return decompressed_blocks


def write_function_blocks(
    *,
    handle,
    decompressor: XpressDecompressor,
    offsets: dict[str, list[dict[str, int]]],
    function_name: str,
    output_dir: Path,
) -> list[dict[str, Any]]:
    blocks = offsets.get(function_name)
    if not blocks:
        print(f"Skip {function_name}: no g_resourceReader->Read calls found.")
        return []

    manifest: list[dict[str, Any]] = []
    for block in read_and_decompress_blocks(handle, decompressor, blocks):
        output_path = output_dir / f"{function_name}_read{block['read_index']}.bin"
        output_path.write_bytes(block["data"])
        entry = {
            "kind": "function_read",
            "function": function_name,
            "read_index": block["read_index"],
            "compressed_offset": block["compressed_offset"],
            "compressed_size": block["compressed_size"],
            "decompressed_size": block["decompressed_size"],
            "output": str(output_path),
        }
        manifest.append(entry)
        print(
            "Extracted "
            f"{function_name} read#{block['read_index']}: "
            f"{human_bytes(block['decompressed_size'])} -> {output_path}"
        )
    return manifest


def write_pso_shader_blobs(
    *,
    handle,
    decompressor: XpressDecompressor,
    offsets: dict[str, list[dict[str, int]]],
    pix_dir: Path,
    pso_id: int,
    output_dir: Path,
    dxc_path: str | None,
) -> list[dict[str, Any]]:
    function_name = find_pso_function(offsets, pso_id)
    stages = parse_pso_stage_lengths(pix_dir, pso_id)
    blocks = read_and_decompress_blocks(handle, decompressor, offsets[function_name])
    data = b"".join(block["data"] for block in blocks)
    expected_size = sum(size for _, size in stages)

    if len(data) != expected_size:
        print(
            f"Warning: PSO {pso_id} decompressed to {human_bytes(len(data))}, "
            f"but parsed shader stages total {human_bytes(expected_size)}. "
            "Splitting by the parsed stage order."
        )

    manifest: list[dict[str, Any]] = []
    cursor = 0
    for stage, size in stages:
        blob = data[cursor : cursor + size]
        cursor += size
        output_path = output_dir / f"pso{pso_id}_{stage}.dxbc"
        output_path.write_bytes(blob)
        magic = blob[:4]
        entry: dict[str, Any] = {
            "kind": "pso_shader",
            "pso": pso_id,
            "function": function_name,
            "stage": stage,
            "declared_size": size,
            "output": str(output_path),
            "magic": magic.hex(),
        }
        print(
            f"Extracted PSO {pso_id} {stage}: "
            f"{human_bytes(len(blob))} magic={magic!r} -> {output_path}"
        )

        if dxc_path and magic == b"DXBC":
            asm_path = output_path.with_suffix(".asm")
            result = subprocess.run(
                [dxc_path, "-dumpbin", str(output_path)],
                capture_output=True,
                text=True,
            )
            asm_text = result.stdout if result.stdout else result.stderr
            asm_path.write_text(asm_text, encoding="utf-8")
            entry["disassembly"] = str(asm_path)
            entry["dxc"] = dxc_path
            entry["dxc_returncode"] = result.returncode
            print(f"Disassembled {asm_path}")
        elif dxc_path:
            entry["disassembly_skipped"] = "shader blob does not start with DXBC"
        else:
            entry["disassembly_skipped"] = "dxc.exe was not found or disabled"

        manifest.append(entry)

    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract decompressed blocks from a PIX on Windows C++ export "
            "resources.bin stream."
        )
    )
    parser.add_argument(
        "--pix-dir",
        type=Path,
        required=True,
        help="Path to the PIX C++ export directory.",
    )
    parser.add_argument(
        "--function",
        action="append",
        default=[],
        help="Replay function name whose g_resourceReader->Read blocks should be extracted.",
    )
    parser.add_argument(
        "--resource",
        action="append",
        type=int,
        default=[],
        help="Resource id to extract, mapped to CreateAndInitResource_<id>.",
    )
    parser.add_argument(
        "--pso",
        action="append",
        type=int,
        default=[],
        help="PSO id whose shader bytecode should be extracted and split by stage.",
    )
    parser.add_argument(
        "--output-dir",
        "--out-dir",
        dest="output_dir",
        type=Path,
        required=True,
        help="Directory for extracted blobs and extraction_manifest.json.",
    )
    parser.add_argument(
        "--dxc",
        help="Optional dxc.exe path. Defaults to PATH, then the newest Windows SDK dxc.exe.",
    )
    parser.add_argument(
        "--no-disasm",
        action="store_true",
        help="Extract shader blobs without running dxc -dumpbin.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pix_dir = args.pix_dir.resolve()
    output_dir = args.output_dir.resolve()

    missing = ensure_required_files(pix_dir)
    if missing:
        raise SystemExit(
            "PIX export directory is missing required files: " + ", ".join(missing)
        )

    functions = list(args.function)
    functions.extend(f"CreateAndInitResource_{resource_id}" for resource_id in args.resource)
    if not functions and not args.pso:
        raise SystemExit("Specify at least one --function, --resource, or --pso.")

    output_dir.mkdir(parents=True, exist_ok=True)
    offsets = build_stream_offsets(pix_dir)
    dxc_path = None if args.no_disasm else find_dxc(args.dxc)
    if not dxc_path and args.pso and not args.no_disasm:
        print("dxc.exe was not found; shader disassembly will be skipped.")

    manifest: dict[str, Any] = {
        "pix_dir": str(pix_dir),
        "output_dir": str(output_dir),
        "dxc": dxc_path,
        "items": [],
    }

    with XpressDecompressor() as decompressor:
        with (pix_dir / "resources.bin").open("rb") as handle:
            for function_name in functions:
                manifest["items"].extend(
                    write_function_blocks(
                        handle=handle,
                        decompressor=decompressor,
                        offsets=offsets,
                        function_name=function_name,
                        output_dir=output_dir,
                    )
                )

            for pso_id in args.pso:
                manifest["items"].extend(
                    write_pso_shader_blobs(
                        handle=handle,
                        decompressor=decompressor,
                        offsets=offsets,
                        pix_dir=pix_dir,
                        pso_id=pso_id,
                        output_dir=output_dir,
                        dxc_path=dxc_path,
                    )
                )

    manifest_path = output_dir / "extraction_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
