from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "CapturedAssets.h",
    "CreatePSOs.cpp",
    "FrameResources_000.cpp",
    "resources.bin",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def sanitize_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return label.strip("._") or "pix_cpp_export"


def human_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(value)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{value} B"


def ensure_required_files(pix_dir: Path) -> list[str]:
    missing = [name for name in REQUIRED_FILES if not (pix_dir / name).exists()]
    missing.extend(
        [
            pattern
            for pattern in ("CreateAndInitResources_*.cpp", "CommandLists_*.cpp")
            if not list(pix_dir.glob(pattern))
        ]
    )
    return missing


def parse_frame_call_order(pix_dir: Path) -> list[str]:
    text = read_text(pix_dir / "FrameResources_000.cpp")
    return re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\(\);", text)


def parse_reader_sizes_by_function(
    pix_dir: Path,
) -> tuple[dict[str, list[int]], dict[str, dict[str, Any]]]:
    read_sizes: dict[str, list[int]] = {}
    locations: dict[str, dict[str, Any]] = {}
    function_re = re.compile(r"^\s*void\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    read_re = re.compile(r"g_resourceReader->Read\([^,]+,\s*(\d+)\)")

    for path in sorted(pix_dir.glob("*.cpp")):
        current_function: str | None = None
        with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
            for line_number, line in enumerate(handle, 1):
                function_match = function_re.search(line)
                if function_match:
                    current_function = function_match.group(1)
                    locations.setdefault(
                        current_function,
                        {
                            "file": path.name,
                            "line": line_number,
                        },
                    )
                    continue

                if current_function is None:
                    continue

                read_match = read_re.search(line)
                if read_match:
                    read_sizes.setdefault(current_function, []).append(
                        int(read_match.group(1))
                    )

    return read_sizes, locations


def classify_frame_function(function_name: str) -> dict[str, Any]:
    resource_match = re.fullmatch(r"CreateAndInitResource_(\d+)", function_name)
    if resource_match:
        return {"kind": "resource", "id": int(resource_match.group(1))}

    graphics_match = re.fullmatch(r"CreateGraphicsPipelineState_(\d+)", function_name)
    if graphics_match:
        return {"kind": "graphics_pso", "id": int(graphics_match.group(1))}

    compute_match = re.fullmatch(r"CreateComputePipelineState_(\d+)", function_name)
    if compute_match:
        return {"kind": "compute_pso", "id": int(compute_match.group(1))}

    return {"kind": "other"}


def build_resource_reader_stream(pix_dir: Path) -> dict[str, Any]:
    read_sizes_by_function, function_locations = parse_reader_sizes_by_function(pix_dir)
    call_order = parse_frame_call_order(pix_dir)

    stream_entries: list[dict[str, Any]] = []
    resource_blocks: dict[int, dict[str, Any]] = {}
    kind_counter: Counter[str] = Counter()
    offset = 0

    for call_index, function_name in enumerate(call_order):
        read_sizes = read_sizes_by_function.get(function_name, [])
        if not read_sizes:
            continue

        classification = classify_frame_function(function_name)
        kind_counter[classification["kind"]] += len(read_sizes)

        for read_index, compressed_size in enumerate(read_sizes):
            entry = {
                "call_index": call_index,
                "function": function_name,
                "read_index": read_index,
                "kind": classification["kind"],
                "compressed_offset": offset,
                "compressed_size": compressed_size,
            }
            if "id" in classification:
                entry["id"] = classification["id"]
            stream_entries.append(entry)

            if classification["kind"] == "resource" and read_index == 0:
                resource_blocks[classification["id"]] = {
                    "function": function_name,
                    "compressed_offset": offset,
                    "compressed_size": compressed_size,
                    **function_locations.get(function_name, {}),
                }

            offset += compressed_size

    return {
        "call_count": len(call_order),
        "functions_with_reads": len(read_sizes_by_function),
        "stream_entry_count": len(stream_entries),
        "compressed_bytes_consumed": offset,
        "kind_counts": dict(kind_counter),
        "resource_block_count": len(resource_blocks),
        "resource_blocks_sample": [
            {"resource_id": key, **value}
            for key, value in sorted(resource_blocks.items())[:25]
        ],
        "stream_sample": stream_entries[:40],
    }


def parse_input_elements(input_layout_text: str) -> list[dict[str, Any]]:
    element_re = re.compile(
        r'\{\s*"([^"]+)",\s*(\d+),\s*(DXGI_FORMAT_[A-Z0-9_]+),\s*'
        r"(\d+),\s*(\d+),\s*(D3D12_INPUT_CLASSIFICATION_[A-Z_]+),\s*(\d+)\s*\}"
    )
    elements = []
    for match in element_re.finditer(input_layout_text):
        elements.append(
            {
                "semantic": match.group(1),
                "semantic_index": int(match.group(2)),
                "format": match.group(3),
                "input_slot": int(match.group(4)),
                "aligned_byte_offset": int(match.group(5)),
                "classification": match.group(6),
                "instance_data_step_rate": int(match.group(7)),
            }
        )
    return elements


def parse_pso_definitions(pix_dir: Path) -> dict[str, Any]:
    path = pix_dir / "CreatePSOs.cpp"
    if not path.exists():
        return {"count": 0, "by_type": {}, "pso_sample": []}

    function_re = re.compile(r"^\s*void\s+Create(Graphics|Compute)PipelineState_(\d+)\s*\(")
    read_re = re.compile(r"g_resourceReader->Read\([^,]+,\s*(\d+)\)")
    root_sig_re = re.compile(r"psoDesc\.pRootSignature\s*=\s*GetRootSignature\((\d+)\)")
    shader_re = re.compile(r"psoDesc\.(VS|PS|DS|HS|GS|CS)\s*=\s*\{[^,]+,\s*(\d+)\s*\}")
    track_re = re.compile(r"CreateAndTrack(?:Graphics|Compute)PipelineState\((\d+),")
    input_layout_re = re.compile(r"D3D12_INPUT_ELEMENT_DESC\s+inputElementDescs\[\]\s*=\s*\{(.*)\};")
    primitive_re = re.compile(
        r"psoDesc\.PrimitiveTopologyType\s*=\s*(D3D12_PRIMITIVE_TOPOLOGY_TYPE_[A-Z_]+)"
    )
    dsv_re = re.compile(r"psoDesc\.DSVFormat\s*=\s*(DXGI_FORMAT_[A-Z0-9_]+)")
    rtv_re = re.compile(r"psoDesc\.RTVFormats\[(\d+)\]\s*=\s*(DXGI_FORMAT_[A-Z0-9_]+)")

    psos: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
        for line_number, line in enumerate(handle, 1):
            function_match = function_re.search(line)
            if function_match:
                if current is not None:
                    psos.append(current)
                current = {
                    "type": function_match.group(1).lower(),
                    "id": int(function_match.group(2)),
                    "function": f"Create{function_match.group(1)}PipelineState_{function_match.group(2)}",
                    "line": line_number,
                    "read_sizes": [],
                    "shader_byte_lengths": {},
                    "input_elements": [],
                    "rtv_formats": {},
                }
                continue

            if current is None:
                continue

            read_match = read_re.search(line)
            if read_match:
                current["read_sizes"].append(int(read_match.group(1)))

            root_match = root_sig_re.search(line)
            if root_match:
                current["root_signature"] = int(root_match.group(1))

            shader_match = shader_re.search(line)
            if shader_match:
                current["shader_byte_lengths"][shader_match.group(1)] = int(
                    shader_match.group(2)
                )

            input_layout_match = input_layout_re.search(line)
            if input_layout_match:
                current["input_elements"] = parse_input_elements(
                    input_layout_match.group(1)
                )

            primitive_match = primitive_re.search(line)
            if primitive_match:
                current["primitive_topology_type"] = primitive_match.group(1)

            dsv_match = dsv_re.search(line)
            if dsv_match:
                current["dsv_format"] = dsv_match.group(1)

            rtv_match = rtv_re.search(line)
            if rtv_match:
                current["rtv_formats"][rtv_match.group(1)] = rtv_match.group(2)

            track_match = track_re.search(line)
            if track_match:
                current["tracked_id"] = int(track_match.group(1))

    if current is not None:
        psos.append(current)

    by_type = Counter(pso["type"] for pso in psos)
    input_layout_counts = Counter(len(pso["input_elements"]) for pso in psos)
    shader_stage_counts: Counter[str] = Counter()
    for pso in psos:
        shader_stage_counts.update(pso["shader_byte_lengths"].keys())

    pso_sample = []
    for pso in psos[:30]:
        pso_sample.append(
            {
                "id": pso["id"],
                "type": pso["type"],
                "line": pso["line"],
                "root_signature": pso.get("root_signature"),
                "read_sizes": pso["read_sizes"],
                "shader_byte_lengths": pso["shader_byte_lengths"],
                "input_element_count": len(pso["input_elements"]),
                "input_elements": pso["input_elements"][:16],
                "primitive_topology_type": pso.get("primitive_topology_type"),
                "dsv_format": pso.get("dsv_format"),
            }
        )

    return {
        "count": len(psos),
        "by_type": dict(by_type),
        "input_layout_element_counts": dict(sorted(input_layout_counts.items())),
        "shader_stage_counts": dict(shader_stage_counts),
        "pso_sample": pso_sample,
        "all_pso_ids_by_type": {
            kind: [pso["id"] for pso in psos if pso["type"] == kind]
            for kind in sorted(by_type)
        },
    }


def limited_append(items: list[dict[str, Any]], entry: dict[str, Any], limit: int) -> None:
    if len(items) < limit:
        items.append(entry)


def parse_command_events(pix_dir: Path, limit: int = 120) -> dict[str, Any]:
    set_pso_re = re.compile(
        r"GetCommandList\((\d+)\)->SetPipelineState\(GetPipelineState\((\d+)\)\)"
    )
    compute_const_re = re.compile(
        r"GetCommandList\((\d+)\)->SetComputeRoot32BitConstant\((\d+),\s*(\d+),\s*(\d+)\)"
    )
    graphics_const_re = re.compile(
        r"GetCommandList\((\d+)\)->SetGraphicsRoot32BitConstant\((\d+),\s*(\d+),\s*(\d+)\)"
    )
    dispatch_re = re.compile(r"GetCommandList\((\d+)\)->Dispatch\((\d+),\s*(\d+),\s*(\d+)\)")
    execute_indirect_re = re.compile(
        r'GetCommandList\((\d+)\)->ExecuteIndirect\(GetCommandSignature\((\d+)\),\s*'
        r'(\d+),\s*g_indirectArgumentBuffers\["([^"]+)"\]'
    )
    draw_indexed_re = re.compile(
        r"GetCommandList\((\d+)\)->DrawIndexedInstanced\((\d+),\s*(\d+),\s*(-?\d+),\s*(-?\d+),\s*(\d+)\)"
    )

    state_by_command_list: defaultdict[int, dict[str, Any]] = defaultdict(dict)
    counts: Counter[str] = Counter()
    command_list_counts: Counter[int] = Counter()
    dispatch_dimensions: Counter[str] = Counter()
    draw_index_counts: Counter[int] = Counter()
    dispatch_32_32_1: list[dict[str, Any]] = []
    dispatch_1_1_1: list[dict[str, Any]] = []
    execute_indirect: list[dict[str, Any]] = []
    draw_indexed: list[dict[str, Any]] = []

    for path in sorted(pix_dir.glob("CommandLists_*.cpp")):
        with path.open("r", encoding="utf-8-sig", errors="ignore") as handle:
            for line_number, line in enumerate(handle, 1):
                set_pso_match = set_pso_re.search(line)
                if set_pso_match:
                    command_list_id = int(set_pso_match.group(1))
                    pso_id = int(set_pso_match.group(2))
                    state_by_command_list[command_list_id]["pso"] = pso_id
                    counts["SetPipelineState"] += 1
                    command_list_counts[command_list_id] += 1
                    continue

                compute_const_match = compute_const_re.search(line)
                if compute_const_match:
                    command_list_id = int(compute_const_match.group(1))
                    state_by_command_list[command_list_id]["compute_root_constant"] = {
                        "root_parameter_index": int(compute_const_match.group(2)),
                        "data": int(compute_const_match.group(3)),
                        "dest_offset": int(compute_const_match.group(4)),
                    }
                    counts["SetComputeRoot32BitConstant"] += 1
                    command_list_counts[command_list_id] += 1
                    continue

                graphics_const_match = graphics_const_re.search(line)
                if graphics_const_match:
                    command_list_id = int(graphics_const_match.group(1))
                    state_by_command_list[command_list_id]["graphics_root_constant"] = {
                        "root_parameter_index": int(graphics_const_match.group(2)),
                        "data": int(graphics_const_match.group(3)),
                        "dest_offset": int(graphics_const_match.group(4)),
                    }
                    counts["SetGraphicsRoot32BitConstant"] += 1
                    command_list_counts[command_list_id] += 1
                    continue

                dispatch_match = dispatch_re.search(line)
                if dispatch_match:
                    command_list_id = int(dispatch_match.group(1))
                    dimensions = tuple(int(dispatch_match.group(index)) for index in (2, 3, 4))
                    dispatch_dimensions[f"{dimensions[0]},{dimensions[1]},{dimensions[2]}"] += 1
                    counts["Dispatch"] += 1
                    command_list_counts[command_list_id] += 1
                    entry = {
                        "file": path.name,
                        "line": line_number,
                        "command_list": command_list_id,
                        "pso": state_by_command_list[command_list_id].get("pso"),
                        "compute_root_constant": state_by_command_list[
                            command_list_id
                        ].get("compute_root_constant"),
                        "dispatch": list(dimensions),
                    }
                    if dimensions == (32, 32, 1):
                        limited_append(dispatch_32_32_1, entry, limit)
                    if dimensions == (1, 1, 1):
                        limited_append(dispatch_1_1_1, entry, limit)
                    continue

                execute_match = execute_indirect_re.search(line)
                if execute_match:
                    command_list_id = int(execute_match.group(1))
                    counts["ExecuteIndirect"] += 1
                    command_list_counts[command_list_id] += 1
                    limited_append(
                        execute_indirect,
                        {
                            "file": path.name,
                            "line": line_number,
                            "command_list": command_list_id,
                            "pso": state_by_command_list[command_list_id].get("pso"),
                            "compute_root_constant": state_by_command_list[
                                command_list_id
                            ].get("compute_root_constant"),
                            "command_signature": int(execute_match.group(2)),
                            "max_command_count": int(execute_match.group(3)),
                            "indirect_argument_buffer": execute_match.group(4),
                        },
                        limit,
                    )
                    continue

                draw_match = draw_indexed_re.search(line)
                if draw_match:
                    command_list_id = int(draw_match.group(1))
                    index_count = int(draw_match.group(2))
                    instance_count = int(draw_match.group(3))
                    draw_index_counts[index_count] += 1
                    counts["DrawIndexedInstanced"] += 1
                    command_list_counts[command_list_id] += 1
                    if instance_count > 1 or index_count in (36, 72, 84, 96, 2040, 4836):
                        limited_append(
                            draw_indexed,
                            {
                                "file": path.name,
                                "line": line_number,
                                "command_list": command_list_id,
                                "pso": state_by_command_list[command_list_id].get("pso"),
                                "graphics_root_constant": state_by_command_list[
                                    command_list_id
                                ].get("graphics_root_constant"),
                                "index_count": index_count,
                                "instance_count": instance_count,
                                "start_index_location": int(draw_match.group(4)),
                                "base_vertex_location": int(draw_match.group(5)),
                                "start_instance_location": int(draw_match.group(6)),
                            },
                            limit,
                        )

    return {
        "counts": dict(counts),
        "command_list_event_counts": dict(command_list_counts.most_common(40)),
        "dispatch_dimensions_top": dict(dispatch_dimensions.most_common(40)),
        "draw_index_counts_top": dict(draw_index_counts.most_common(40)),
        "candidates": {
            "dispatch_32_32_1": dispatch_32_32_1,
            "dispatch_1_1_1": dispatch_1_1_1,
            "execute_indirect": execute_indirect,
            "draw_indexed_instanced": draw_indexed,
        },
    }


def parse_captured_assets_summary(pix_dir: Path) -> dict[str, Any]:
    path = pix_dir / "CapturedAssets.h"
    if not path.exists():
        return {"resource_init_info_count": 0}

    text = read_text(path)
    resource_ids = [int(value) for value in re.findall(r"g_resourceInitInfo_(\d+)_0", text)]
    format_counter = Counter(re.findall(r"DXGI_FORMAT_[A-Z0-9_]+", text))
    dimensions_counter = Counter(
        f"{width}x{height}x{depth}"
        for _, width, height, depth, _, _ in re.findall(
            r"\{\s*\d+,\s*\{\s*(DXGI_FORMAT_[A-Z0-9_]+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\s*\},\s*(\d+)\s*\}",
            text,
        )
    )
    return {
        "resource_init_info_count": len(set(resource_ids)),
        "resource_init_info_min_id": min(resource_ids) if resource_ids else None,
        "resource_init_info_max_id": max(resource_ids) if resource_ids else None,
        "format_counts_top": dict(format_counter.most_common(25)),
        "dimensions_top": dict(dimensions_counter.most_common(25)),
    }


def collect_export_index(pix_dir: Path, label: str) -> dict[str, Any]:
    missing = ensure_required_files(pix_dir)
    if missing:
        raise FileNotFoundError(
            f"PIX export directory is missing required files: {', '.join(missing)}"
        )

    resources_bin = pix_dir / "resources.bin"
    cpp_files = sorted(pix_dir.glob("*.cpp"))

    reader_stream = build_resource_reader_stream(pix_dir)
    pso_summary = parse_pso_definitions(pix_dir)
    command_summary = parse_command_events(pix_dir)
    captured_assets = parse_captured_assets_summary(pix_dir)

    return {
        "label": label,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pix_dir": str(pix_dir),
        "file_summary": {
            "cpp_file_count": len(cpp_files),
            "create_and_init_resource_file_count": len(
                list(pix_dir.glob("CreateAndInitResources_*.cpp"))
            ),
            "command_list_file_count": len(list(pix_dir.glob("CommandLists_*.cpp"))),
            "resources_bin_size": resources_bin.stat().st_size,
            "resources_bin_size_human": human_bytes(resources_bin.stat().st_size),
        },
        "resource_reader_stream": reader_stream,
        "captured_assets": captured_assets,
        "pipeline_states": pso_summary,
        "command_events": command_summary,
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        output.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(output)


def root_constant_text(entry: dict[str, Any], key: str = "compute_root_constant") -> str:
    value = entry.get(key)
    if not value:
        return ""
    return f"root{value['root_parameter_index']}={value['data']}@{value['dest_offset']}"


def render_event_rows(events: list[dict[str, Any]], columns: list[str]) -> list[list[Any]]:
    rows = []
    for event in events:
        row = []
        for column in columns:
            if column == "loc":
                row.append(f"{event.get('file')}:{event.get('line')}")
            elif column == "dispatch":
                row.append(",".join(str(value) for value in event.get("dispatch", [])))
            elif column == "compute_root_constant":
                row.append(root_constant_text(event))
            elif column == "graphics_root_constant":
                row.append(root_constant_text(event, "graphics_root_constant"))
            else:
                row.append(event.get(column, ""))
        rows.append(row)
    return rows


def render_markdown(index: dict[str, Any]) -> str:
    files = index["file_summary"]
    reader = index["resource_reader_stream"]
    pso = index["pipeline_states"]
    commands = index["command_events"]
    captured = index["captured_assets"]
    candidates = commands["candidates"]

    lines = [
        f"# PIX C++ 导出索引：{index['label']}",
        "",
        f"- 生成时间：`{index['generated_at']}`",
        f"- 源目录：`{index['pix_dir']}`",
        "",
        "## 概览",
        "",
        markdown_table(
            ["项目", "值"],
            [
                ["C++ 文件数", files["cpp_file_count"]],
                ["CreateAndInitResources 文件数", files["create_and_init_resource_file_count"]],
                ["CommandLists 文件数", files["command_list_file_count"]],
                ["resources.bin 大小", files["resources_bin_size_human"]],
                ["FrameResources 调用数", reader["call_count"]],
                ["resourceReader 读取块数", reader["stream_entry_count"]],
                ["resourceReader 已消费压缩字节", human_bytes(reader["compressed_bytes_consumed"])],
                ["resource 初始化块数", reader["resource_block_count"]],
                ["CapturedAssets init info 数", captured["resource_init_info_count"]],
                ["PSO 总数", pso["count"]],
                ["命令事件计数", commands["counts"]],
            ],
        ),
        "",
        "## resourceReader 读流",
        "",
        "PIX C++ replay 的 `resources.bin` 读流不仅包含资源块，也包含 PSO shader bytecode 等块。定位资源压缩偏移时必须按 `FrameResources_000.cpp` 的调用顺序累计所有 `g_resourceReader->Read`，不能只累计 `CreateAndInitResource_*`。",
        "",
        markdown_table(
            ["类型", "读取块数"],
            [[key, value] for key, value in sorted(reader["kind_counts"].items())],
        ),
        "",
        "### 资源块样本",
        "",
        markdown_table(
            ["resource id", "offset", "compressed size", "定义位置"],
            [
                [
                    item["resource_id"],
                    item["compressed_offset"],
                    item["compressed_size"],
                    f"{item.get('file', '')}:{item.get('line', '')}",
                ]
                for item in reader["resource_blocks_sample"]
            ],
        ),
        "",
        "## PSO 摘要",
        "",
        markdown_table(
            ["项目", "值"],
            [
                ["按类型计数", pso["by_type"]],
                ["shader stage 计数", pso["shader_stage_counts"]],
                ["input layout 元素数分布", pso["input_layout_element_counts"]],
            ],
        ),
        "",
        "### PSO 样本",
        "",
        markdown_table(
            ["PSO", "类型", "行", "root signature", "shader bytes", "input elements"],
            [
                [
                    item["id"],
                    item["type"],
                    item["line"],
                    item.get("root_signature", ""),
                    item["shader_byte_lengths"],
                    item["input_element_count"],
                ]
                for item in pso["pso_sample"][:20]
            ],
        ),
        "",
        "## 命令候选",
        "",
        "以下只是按命令形态筛出的候选事件。给事件命名为某个业务 pass 前，需要继续用 root 参数、descriptor、buffer/texture 绑定、shader 访问和资源内容闭合验证。",
        "",
        "### Dispatch(32,32,1)",
        "",
        markdown_table(
            ["位置", "cmdlist", "pso", "root constant", "dispatch"],
            render_event_rows(
                candidates["dispatch_32_32_1"][:40],
                ["loc", "command_list", "pso", "compute_root_constant", "dispatch"],
            ),
        ),
        "",
        "### Dispatch(1,1,1)",
        "",
        markdown_table(
            ["位置", "cmdlist", "pso", "root constant", "dispatch"],
            render_event_rows(
                candidates["dispatch_1_1_1"][:40],
                ["loc", "command_list", "pso", "compute_root_constant", "dispatch"],
            ),
        ),
        "",
        "### ExecuteIndirect",
        "",
        markdown_table(
            ["位置", "cmdlist", "pso", "root constant", "signature", "max count", "argument buffer"],
            render_event_rows(
                candidates["execute_indirect"][:60],
                [
                    "loc",
                    "command_list",
                    "pso",
                    "compute_root_constant",
                    "command_signature",
                    "max_command_count",
                    "indirect_argument_buffer",
                ],
            ),
        ),
        "",
        "### DrawIndexedInstanced 样本",
        "",
        markdown_table(
            ["位置", "cmdlist", "pso", "graphics root", "index count", "instance count", "start instance"],
            render_event_rows(
                candidates["draw_indexed_instanced"][:60],
                [
                    "loc",
                    "command_list",
                    "pso",
                    "graphics_root_constant",
                    "index_count",
                    "instance_count",
                    "start_instance_location",
                ],
            ),
        ),
        "",
        "## 高频统计",
        "",
        markdown_table(
            ["Dispatch 维度", "次数"],
            [[key, value] for key, value in commands["dispatch_dimensions_top"].items()],
        ),
        "",
        markdown_table(
            ["Draw index count", "次数"],
            [[key, value] for key, value in commands["draw_index_counts_top"].items()],
        ),
        "",
        "## 使用边界",
        "",
        "- 事件号、PSO id、descriptor id 在不同截帧之间可能漂移；复查新帧时先重新生成索引。",
        "- 本报告不直接证明业务语义，只提供稳定入口：读流、PSO、命令形态、候选事件位置。",
        "- 下一步若要提取资源，先从索引中的 PSO/root/descriptor 线索反推资源 id，再调用专门的提取脚本。",
        "",
    ]
    return "\n".join(lines)


def write_outputs(index: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "pix_cpp_export_index.json"
    markdown_path = output_dir / "pix_cpp_export_index.md"
    json_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(index), encoding="utf-8")
    return json_path, markdown_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Index a PIX on Windows C++ export for repeatable reverse analysis."
    )
    parser.add_argument(
        "--pix-dir",
        required=True,
        type=Path,
        help="Path to the PIX C++ export directory.",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Report label. Defaults to the export directory name.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".pix-analysis/pix-cpp-export-indexes"),
        help="Directory that receives <label>/pix_cpp_export_index.{json,md}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pix_dir = args.pix_dir.resolve()
    label = sanitize_label(args.label or pix_dir.name)
    output_dir = args.output_dir / label
    index = collect_export_index(pix_dir, label)
    json_path, markdown_path = write_outputs(index, output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
