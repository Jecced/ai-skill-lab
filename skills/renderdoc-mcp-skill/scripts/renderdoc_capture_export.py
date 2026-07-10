#!/usr/bin/env python3
"""Export event-scoped evidence through qrenderdoc's embedded RenderDoc module."""

import argparse
import hashlib
import json
import os
import re
import sys
import traceback


rd = None
CAPTURE_PATH = ""
OUT_DIR = ""
TARGET_EIDS = []


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--capture",
        default=os.environ.get("RENDERDOC_EXPORT_CAPTURE"),
        help="Path to an authorized .rdc capture; qrenderdoc automation can use RENDERDOC_EXPORT_CAPTURE",
    )
    parser.add_argument(
        "--out-dir",
        default=os.environ.get("RENDERDOC_EXPORT_OUT_DIR"),
        help="Evidence directory; qrenderdoc automation can use RENDERDOC_EXPORT_OUT_DIR",
    )
    parser.add_argument(
        "--events",
        default=os.environ.get("RENDERDOC_EXPORT_EVENTS"),
        help="Comma-separated EIDs; qrenderdoc automation can use RENDERDOC_EXPORT_EVENTS",
    )
    args, _ = parser.parse_known_args()
    if not args.capture or not args.out_dir or not args.events:
        parser.error("capture, out-dir, and events are required through arguments or RENDERDOC_EXPORT_* variables")
    events = [int(item.strip()) for item in args.events.split(",") if item.strip()]
    if not events:
        parser.error("--events must contain at least one event ID")
    return os.path.abspath(args.capture), os.path.abspath(args.out_dir), events


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def safe_name(value):
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value)).strip("_")


def rid_str(resource_id):
    return str(resource_id)


def rid_short(resource_id):
    return rid_str(resource_id).replace("ResourceId::", "rid_").replace("ResourceId", "rid")


def is_null_rid(resource_id):
    return resource_id == rd.ResourceId.Null() or rid_str(resource_id) in ("ResourceId::0", "ResourceId()")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(path):
    return os.path.relpath(path, OUT_DIR).replace("\\", "/")


def file_record(path, extra=None):
    record = {
        "path": relative_path(path),
        "bytes": os.path.getsize(path),
        "sha256": sha256_file(path),
    }
    if extra:
        record.update(extra)
    return record


def write_json(path, data):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_bytes(path, data):
    ensure_dir(os.path.dirname(path))
    with open(path, "wb") as stream:
        stream.write(bytes(data))
    return file_record(path)


def enum_text(value):
    try:
        return str(value)
    except Exception:
        return ""


def format_dict(fmt):
    try:
        name = str(fmt.Name())
    except Exception:
        name = str(fmt)
    try:
        srgb = bool(fmt.SRGBCorrected())
    except Exception:
        srgb = False
    try:
        bgra = bool(fmt.BGRAOrder())
    except Exception:
        bgra = False
    return {
        "name": name,
        "type": enum_text(getattr(fmt, "type", "")),
        "compCount": int(getattr(fmt, "compCount", 0)),
        "compByteWidth": int(getattr(fmt, "compByteWidth", 0)),
        "compType": enum_text(getattr(fmt, "compType", "")),
        "srgb": srgb,
        "bgra": bgra,
    }


def texture_dict(tex):
    return {
        "resourceId": rid_str(tex.resourceId),
        "format": format_dict(tex.format),
        "dimension": int(tex.dimension),
        "type": enum_text(tex.type),
        "width": int(tex.width),
        "height": int(tex.height),
        "depth": int(tex.depth),
        "cubemap": bool(tex.cubemap),
        "mips": int(tex.mips),
        "arraySize": int(tex.arraysize),
        "sampleCount": int(tex.msSamp),
        "sampleQuality": int(tex.msQual),
        "byteSize": int(tex.byteSize),
        "creationFlags": enum_text(tex.creationFlags),
    }


def buffer_dict(buf):
    return {
        "resourceId": rid_str(buf.resourceId),
        "length": int(buf.length),
        "gpuAddress": int(buf.gpuAddress),
        "creationFlags": enum_text(buf.creationFlags),
    }


def descriptor_dict(desc):
    return {
        "type": enum_text(getattr(desc, "type", "")),
        "flags": enum_text(getattr(desc, "flags", "")),
        "format": format_dict(desc.format),
        "resource": rid_str(desc.resource),
        "secondary": rid_str(desc.secondary),
        "view": rid_str(desc.view),
        "byteOffset": int(desc.byteOffset),
        "byteSize": int(desc.byteSize),
        "counterByteOffset": int(desc.counterByteOffset),
        "bufferStructCount": int(desc.bufferStructCount),
        "elementByteSize": int(desc.elementByteSize),
        "firstSlice": int(desc.firstSlice),
        "numSlices": int(desc.numSlices),
        "firstMip": int(desc.firstMip),
        "numMips": int(desc.numMips),
        "textureType": enum_text(desc.textureType),
    }


def sampler_dict(sampler):
    try:
        return {
            "object": rid_str(sampler.object),
            "type": enum_text(sampler.type),
            "addressU": enum_text(sampler.addressU),
            "addressV": enum_text(sampler.addressV),
            "addressW": enum_text(sampler.addressW),
            "compareFunction": enum_text(sampler.compareFunction),
            "filter": enum_text(sampler.filter),
            "srgbBorder": bool(sampler.srgbBorder),
            "seamlessCubemaps": bool(sampler.seamlessCubemaps),
            "unnormalized": bool(sampler.unnormalized),
            "maxAnisotropy": float(sampler.maxAnisotropy),
            "maxLOD": float(sampler.maxLOD),
            "minLOD": float(sampler.minLOD),
            "mipBias": float(sampler.mipBias),
            "borderColorType": enum_text(sampler.borderColorType),
        }
    except Exception as exc:
        return {"error": repr(exc)}


def access_dict(access):
    return {
        "stage": enum_text(access.stage),
        "type": enum_text(access.type),
        "index": int(access.index),
        "arrayElement": int(access.arrayElement),
        "descriptorStore": rid_str(access.descriptorStore),
        "byteOffset": int(access.byteOffset),
        "byteSize": int(access.byteSize),
        "staticallyUnused": bool(access.staticallyUnused),
    }


def constant_type_dict(value):
    return {
        "name": str(value.name),
        "baseType": enum_text(value.baseType),
        "rows": int(value.rows),
        "columns": int(value.columns),
        "flags": enum_text(value.flags),
        "elements": int(value.elements),
        "arrayByteStride": int(value.arrayByteStride),
        "matrixByteStride": int(value.matrixByteStride),
        "members": [constant_dict(member) for member in value.members],
    }


def constant_dict(value):
    return {
        "name": str(value.name),
        "byteOffset": int(value.byteOffset),
        "type": constant_type_dict(value.type),
    }


def shader_resource_dict(resource):
    return {
        "name": str(resource.name),
        "descriptorType": enum_text(resource.descriptorType),
        "textureType": enum_text(resource.textureType),
        "fixedBindSetOrSpace": int(resource.fixedBindSetOrSpace),
        "fixedBindNumber": int(resource.fixedBindNumber),
        "bindArraySize": int(resource.bindArraySize),
        "isTexture": bool(resource.isTexture),
        "hasSampler": bool(resource.hasSampler),
        "isInputAttachment": bool(resource.isInputAttachment),
        "isReadOnly": bool(resource.isReadOnly),
    }


def constant_block_dict(block):
    return {
        "name": str(block.name),
        "fixedBindSetOrSpace": int(block.fixedBindSetOrSpace),
        "fixedBindNumber": int(block.fixedBindNumber),
        "bindArraySize": int(block.bindArraySize),
        "byteSize": int(block.byteSize),
        "bufferBacked": bool(block.bufferBacked),
        "variables": [constant_dict(value) for value in block.variables],
    }


def reflection_dict(reflection):
    return {
        "resourceId": rid_str(reflection.resourceId),
        "entryPoint": str(reflection.entryPoint),
        "stage": enum_text(reflection.stage),
        "encoding": enum_text(reflection.encoding),
        "constantBlocks": [constant_block_dict(value) for value in reflection.constantBlocks],
        "readOnlyResources": [shader_resource_dict(value) for value in reflection.readOnlyResources],
        "readWriteResources": [shader_resource_dict(value) for value in reflection.readWriteResources],
        "samplers": [
            {
                "name": str(value.name),
                "fixedBindSetOrSpace": int(value.fixedBindSetOrSpace),
                "fixedBindNumber": int(value.fixedBindNumber),
                "bindArraySize": int(value.bindArraySize),
            }
            for value in reflection.samplers
        ],
        "inputSignature": [str(value) for value in reflection.inputSignature],
        "outputSignature": [str(value) for value in reflection.outputSignature],
    }


def shader_binding(reflection, category, index):
    try:
        if category == "constantBlock":
            return constant_block_dict(reflection.constantBlocks[index])
        if category == "readOnlyResource":
            return shader_resource_dict(reflection.readOnlyResources[index])
        if category == "readWriteResource":
            return shader_resource_dict(reflection.readWriteResources[index])
        if category == "sampler":
            value = reflection.samplers[index]
            return {
                "name": str(value.name),
                "fixedBindSetOrSpace": int(value.fixedBindSetOrSpace),
                "fixedBindNumber": int(value.fixedBindNumber),
                "bindArraySize": int(value.bindArraySize),
            }
    except Exception:
        return None
    return None


def used_descriptor_dict(used, reflection, category):
    return {
        "category": category,
        "access": access_dict(used.access),
        "descriptor": descriptor_dict(used.descriptor),
        "sampler": sampler_dict(used.sampler),
        "shaderBinding": shader_binding(reflection, category, int(used.access.index)),
    }


class ExportContext:
    def __init__(self, controller):
        self.controller = controller
        self.textures = {rid_str(value.resourceId): value for value in controller.GetTextures()}
        self.buffers = {rid_str(value.resourceId): value for value in controller.GetBuffers()}
        self.resources = {rid_str(value.resourceId): value for value in controller.GetResources()}
        self.exported_textures = {}
        self.exported_buffers = {}
        self.exported_shaders = {}

    def export_texture(self, resource_id, reason):
        if is_null_rid(resource_id):
            return None
        key = rid_str(resource_id)
        if key in self.exported_textures:
            self.exported_textures[key]["reasons"].append(reason)
            return self.exported_textures[key]
        texture = self.textures.get(key)
        if texture is None:
            return {"resourceId": key, "error": "not a texture", "reasons": [reason]}
        info = texture_dict(texture)
        base = "%s_%s_%sx%sx%s" % (
            rid_short(resource_id),
            safe_name(info["format"]["name"]),
            texture.width,
            texture.height,
            texture.depth,
        )
        output_dir = os.path.join(OUT_DIR, "resources", "textures")
        ensure_dir(output_dir)
        files = {}
        dds_path = os.path.join(output_dir, base + ".dds")
        try:
            save = rd.TextureSave()
            save.resourceId = resource_id
            save.destType = rd.FileType.DDS
            save.mip = -1
            result = self.controller.SaveTexture(save, dds_path)
            files["dds"] = file_record(dds_path, {"result": str(result)}) if os.path.exists(dds_path) else {"path": relative_path(dds_path), "result": str(result), "missing": True}
        except Exception as exc:
            files["dds"] = {"path": relative_path(dds_path), "error": repr(exc)}
        raw_path = os.path.join(output_dir, base + ".sub0.raw")
        try:
            files["rawSubresource0"] = write_bytes(raw_path, self.controller.GetTextureData(resource_id, rd.Subresource()))
        except Exception as exc:
            files["rawSubresource0"] = {"path": relative_path(raw_path), "error": repr(exc)}
        info["files"] = files
        info["reasons"] = [reason]
        self.exported_textures[key] = info
        return info

    def export_buffer(self, resource_id, byte_offset, byte_size, reason):
        if is_null_rid(resource_id):
            return None
        key = "%s:%s:%s" % (rid_str(resource_id), int(byte_offset), int(byte_size))
        if key in self.exported_buffers:
            self.exported_buffers[key]["reasons"].append(reason)
            return self.exported_buffers[key]
        buffer = self.buffers.get(rid_str(resource_id))
        info = {
            "resourceId": rid_str(resource_id),
            "byteOffset": int(byte_offset),
            "byteSize": int(byte_size),
            "buffer": buffer_dict(buffer) if buffer else None,
            "reasons": [reason],
        }
        size_name = "all" if int(byte_size) == 0 else str(int(byte_size))
        path = os.path.join(OUT_DIR, "resources", "buffers", "%s_off_%s_size_%s.bin" % (rid_short(resource_id), int(byte_offset), size_name))
        try:
            info["file"] = write_bytes(path, self.controller.GetBufferData(resource_id, int(byte_offset), int(byte_size)))
        except Exception as exc:
            info["file"] = {"path": relative_path(path), "error": repr(exc)}
        self.exported_buffers[key] = info
        return info

    def export_shader(self, eid, stage_name, pipeline_id, reflection, disassembly):
        key = "%s:%s:%s" % (eid, stage_name, rid_str(reflection.resourceId))
        if key in self.exported_shaders:
            return self.exported_shaders[key]
        output_dir = os.path.join(OUT_DIR, "eid_%s" % eid, "shaders")
        ensure_dir(output_dir)
        base = "eid_%s_%s_%s_%s" % (eid, stage_name, rid_short(reflection.resourceId), safe_name(reflection.encoding))
        info = {
            "stage": stage_name,
            "resourceId": rid_str(reflection.resourceId),
            "entryPoint": str(reflection.entryPoint),
            "encoding": str(reflection.encoding),
        }
        binary_path = os.path.join(output_dir, base + ".bin")
        try:
            info["rawBytes"] = write_bytes(binary_path, reflection.rawBytes)
            if "SPIRV" in str(reflection.encoding).upper() or "SPIR-V" in str(reflection.encoding).upper():
                info["spirvAlias"] = write_bytes(os.path.join(output_dir, base + ".spv"), reflection.rawBytes)
        except Exception as exc:
            info["rawBytes"] = {"path": relative_path(binary_path), "error": repr(exc)}
        disasm_path = os.path.join(output_dir, base + ".disasm.txt")
        try:
            with open(disasm_path, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(disassembly)
            info["disassembly"] = file_record(disasm_path, {"pipeline": rid_str(pipeline_id)})
        except Exception as exc:
            info["disassembly"] = {"path": relative_path(disasm_path), "error": repr(exc)}
        self.exported_shaders[key] = info
        return info


def stage_enums():
    result = []
    for label, enum_name in [
        ("vs", "Vertex"),
        ("hs", "Tess_Control"),
        ("ds", "Tess_Eval"),
        ("gs", "Geometry"),
        ("ps", "Fragment"),
        ("cs", "Compute"),
        ("task", "Task"),
        ("mesh", "Mesh"),
    ]:
        value = getattr(rd.ShaderStage, enum_name, None)
        if value is not None:
            result.append((label, value))
    return result


def attach_resource_export(context, entry, reason):
    descriptor = entry["descriptor"]
    resource_id = descriptor["resource"]
    if resource_id in context.textures:
        entry["textureExport"] = context.export_texture(entry["_resourceObject"], reason)
    elif resource_id in context.buffers:
        entry["bufferExport"] = context.export_buffer(
            entry["_resourceObject"], descriptor["byteOffset"], descriptor["byteSize"], reason
        )
    entry.pop("_resourceObject", None)


def export_event(context, eid):
    controller = context.controller
    controller.SetFrameEvent(eid, False)
    pipeline = controller.GetPipelineState()
    pipeline_id = pipeline.GetGraphicsPipelineObject()
    record = {
        "eventId": eid,
        "graphicsPipelineObject": rid_str(pipeline_id),
        "computePipelineObject": rid_str(pipeline.GetComputePipelineObject()),
        "outputTargets": [],
        "depthTarget": None,
        "stages": {},
        "allDescriptorAccess": [],
    }
    for index, target in enumerate(pipeline.GetOutputTargets()):
        entry = descriptor_dict(target)
        entry["targetIndex"] = index
        entry["export"] = context.export_texture(target.resource, "eid_%s:output%s" % (eid, index))
        record["outputTargets"].append(entry)
    depth = pipeline.GetDepthTarget()
    record["depthTarget"] = descriptor_dict(depth)
    if not is_null_rid(depth.resource):
        record["depthTarget"]["export"] = context.export_texture(depth.resource, "eid_%s:depth" % eid)
    try:
        record["allDescriptorAccess"] = [access_dict(value) for value in pipeline.GetDescriptorAccess()]
    except Exception as exc:
        record["allDescriptorAccessError"] = repr(exc)

    for stage_name, stage in stage_enums():
        shader_id = pipeline.GetShader(stage)
        if is_null_rid(shader_id):
            continue
        reflection = pipeline.GetShaderReflection(stage)
        if reflection is None:
            continue
        try:
            disassembly = controller.DisassembleShader(pipeline_id, reflection, "")
        except Exception as exc:
            disassembly = "DISASSEMBLY_ERROR: %r" % exc
        stage_record = {
            "shaderId": rid_str(shader_id),
            "entryPoint": str(pipeline.GetShaderEntryPoint(stage)),
            "reflection": reflection_dict(reflection),
            "shaderExport": context.export_shader(eid, stage_name, pipeline_id, reflection, disassembly),
            "constantBlocks": [],
            "readOnlyResources": [],
            "readWriteResources": [],
            "samplers": [],
        }
        for used in pipeline.GetConstantBlocks(stage, True):
            entry = used_descriptor_dict(used, reflection, "constantBlock")
            descriptor = used.descriptor
            entry["bufferExport"] = context.export_buffer(
                descriptor.resource,
                descriptor.byteOffset,
                descriptor.byteSize,
                "eid_%s:%s:cb%s" % (eid, stage_name, int(used.access.index)),
            )
            stage_record["constantBlocks"].append(entry)
        for category, getter, destination in [
            ("readOnlyResource", pipeline.GetReadOnlyResources, "readOnlyResources"),
            ("readWriteResource", pipeline.GetReadWriteResources, "readWriteResources"),
        ]:
            for used in getter(stage, True):
                entry = used_descriptor_dict(used, reflection, category)
                entry["_resourceObject"] = used.descriptor.resource
                attach_resource_export(
                    context,
                    entry,
                    "eid_%s:%s:%s%s" % (eid, stage_name, category, int(used.access.index)),
                )
                stage_record[destination].append(entry)
        for used in pipeline.GetSamplers(stage, True):
            stage_record["samplers"].append(used_descriptor_dict(used, reflection, "sampler"))
        record["stages"][stage_name] = stage_record

    event_path = os.path.join(OUT_DIR, "eid_%s" % eid, "exact_state.json")
    write_json(event_path, record)
    record["stateFile"] = file_record(event_path)
    return record


def api_properties(controller):
    try:
        props = controller.GetAPIProperties()
        return {
            "pipelineType": enum_text(props.pipelineType),
            "localRenderer": enum_text(props.localRenderer),
            "remoteReplay": bool(props.remoteReplay),
            "degraded": bool(props.degraded),
        }
    except Exception as exc:
        return {"error": repr(exc)}


def run_export(controller):
    ensure_dir(OUT_DIR)
    context = ExportContext(controller)
    summary = {
        "schema": 1,
        "capture": CAPTURE_PATH,
        "targetEids": TARGET_EIDS,
        "api": api_properties(controller),
        "resources": {
            "textureCount": len(context.textures),
            "bufferCount": len(context.buffers),
            "resourceCount": len(context.resources),
        },
        "events": [],
    }
    for eid in TARGET_EIDS:
        print("renderdoc_export: event", eid)
        try:
            summary["events"].append(export_event(context, eid))
        except Exception as exc:
            summary["events"].append({"eventId": eid, "error": repr(exc), "traceback": traceback.format_exc()})
    summary["exportedTextures"] = list(context.exported_textures.values())
    summary["exportedBuffers"] = list(context.exported_buffers.values())
    summary["exportedShaders"] = list(context.exported_shaders.values())
    manifest = os.path.join(OUT_DIR, "exact_export_manifest.json")
    write_json(manifest, summary)
    print("renderdoc_export: manifest", manifest)


def main():
    global rd, CAPTURE_PATH, OUT_DIR, TARGET_EIDS
    CAPTURE_PATH, OUT_DIR, TARGET_EIDS = parse_args()
    ensure_dir(OUT_DIR)
    status_path = os.path.join(OUT_DIR, "export_status.json")
    status = {
        "state": "starting",
        "capture": CAPTURE_PATH,
        "targetEids": TARGET_EIDS,
        "python": sys.version,
    }
    write_json(status_path, status)
    if not os.path.isfile(CAPTURE_PATH):
        status.update({"state": "error", "error": "capture not found"})
        write_json(status_path, status)
        raise SystemExit("capture not found: %s" % CAPTURE_PATH)
    try:
        import renderdoc as renderdoc_module
    except ImportError as exc:
        status.update({"state": "error", "error": repr(exc)})
        write_json(status_path, status)
        raise SystemExit("Run this script through qrenderdoc --python; the renderdoc module is unavailable: %s" % exc)
    rd = renderdoc_module
    print("renderdoc_export: loading", CAPTURE_PATH)
    capture = rd.OpenCaptureFile()
    controller = None
    try:
        open_result = capture.OpenFile(CAPTURE_PATH, "", None)
        open_code = getattr(open_result, "code", open_result)
        if open_code != rd.ResultCode.Succeeded:
            raise RuntimeError("could not open capture: %s" % open_result)
        if not capture.LocalReplaySupport():
            raise RuntimeError("capture does not have local replay support")
        replay_result, controller = capture.OpenCapture(rd.ReplayOptions(), None)
        replay_code = getattr(replay_result, "code", replay_result)
        if replay_code != rd.ResultCode.Succeeded:
            raise RuntimeError("could not initialise replay: %s" % replay_result)
        run_export(controller)
        status.update({"state": "complete", "manifest": "exact_export_manifest.json"})
        write_json(status_path, status)
    except Exception as exc:
        status.update({"state": "error", "error": repr(exc), "traceback": traceback.format_exc()})
        write_json(status_path, status)
        raise
    finally:
        if controller is not None:
            controller.Shutdown()
        capture.Shutdown()
    print("renderdoc_export: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
