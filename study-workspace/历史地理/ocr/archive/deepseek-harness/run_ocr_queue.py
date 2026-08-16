#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek Harness OCR 队列执行器
================================
- 读取队列 JSONL（只读）
- 输出到 D:\\workspace\\历史地理\\ocr\\deepseek-harness
- 逐页 OCR（GPU 优先），即用即删临时页图
- 断点续跑：manifest + checkpoint + 已生成 page_text 判断
"""
import os
import json
import sys
import time
import hashlib
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

# 固定路径；可用环境变量覆盖（测试用）
QUEUE_PATH = Path(os.environ.get("OCR_QUEUE_PATH", r"C:\Users\30374\Documents\ChatGPT\考研\study-workspace\历史地理\milestone0\DeepSeek_Harness_OCR_队列.jsonl"))
OUT_ROOT = Path(os.environ.get("OCR_OUTPUT_ROOT", r"D:\workspace\历史地理\ocr\deepseek-harness"))
FILES_DIR = OUT_ROOT / "files"
PROGRESS_DIR = OUT_ROOT / "progress_reports"
ERROR_LOG = OUT_ROOT / "error.log"
MANIFEST = OUT_ROOT / "manifest.jsonl"
CHECKPOINT = OUT_ROOT / "checkpoint.json"
GPU_INFO = OUT_ROOT / "gpu_info.json"
VERSIONS = OUT_ROOT / "versions.json"

DPI = 200
PROGRESS_INTERVAL = 300  # 秒

CST = timezone(timedelta(hours=8))


def now_str():
    return datetime.now(CST).isoformat(timespec="seconds")


def log_error(msg):
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"{now_str()} {msg}\n")


def load_queue():
    rows = []
    with open(QUEUE_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_manifest():
    data = {}
    if MANIFEST.exists():
        with open(MANIFEST, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    data[row.get("sha256")] = row
    return data


def save_manifest(entries):
    tmp = MANIFEST.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    tmp.replace(MANIFEST)


def load_checkpoint():
    if CHECKPOINT.exists():
        with open(CHECKPOINT, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(cp):
    tmp = CHECKPOINT.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cp, f, ensure_ascii=False, indent=2)
    tmp.replace(CHECKPOINT)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_ocr_engine():
    """构建 GPU OCR 引擎；若 CUDA 不可用则回退 CPU 并写明原因。
    注意：不要在此导入 torch，torch 会初始化 CUDA 并拖慢 onnxruntime CUDA 推理。
    """
    import onnxruntime as ort
    from rapidocr import RapidOCR, EngineType, OCRVersion, ModelType

    device = "cuda"
    reason = None
    if "CUDAExecutionProvider" not in ort.get_available_providers():
        device = "cpu"
        reason = "onnxruntime CUDAExecutionProvider not available"

    resources = Path(r"D:\workspace\ocr-venv\Lib\site-packages\rapid_doc\resources")
    params = {
        "Det.engine_type": EngineType.ONNXRUNTIME,
        "Rec.engine_type": EngineType.ONNXRUNTIME,
        "Det.ocr_version": OCRVersion.PPOCRV6,
        "Rec.ocr_version": OCRVersion.PPOCRV6,
        "Det.model_type": ModelType.SMALL,
        "Rec.model_type": ModelType.SMALL,
        "Det.model_path": str(resources / "PP-OCRv6_det_small.onnx"),
        "Rec.model_path": str(resources / "PP-OCRv6_rec_small.onnx"),
        "Rec.rec_keys_path": str(resources / "ppocrv6_dict.txt"),
    }
    if device == "cuda":
        params["EngineConfig.onnxruntime.use_cuda"] = True
        params["EngineConfig.onnxruntime.cuda_ep_cfg.device_id"] = 0

    engine = RapidOCR(params=params)
    providers = []
    try:
        providers = engine.text_det.session.session.get_providers()
    except Exception:
        providers = []

    gpu_name = None
    gpu_mem_gb = None
    try:
        import subprocess
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
        if out:
            parts = out.split(",")
            gpu_name = parts[0].strip()
            try:
                gpu_mem_gb = round(int(parts[1].strip()) / 1024, 2)
            except Exception:
                gpu_mem_gb = None
    except Exception:
        pass

    info = {
        "device": device,
        "fallback_reason": reason,
        "gpu_name": gpu_name,
        "gpu_total_mem_gb": gpu_mem_gb,
        "ort_version": ort.__version__,
        "ort_available_providers": ort.get_available_providers(),
        "ocr_actual_providers": providers,
        "engine": "RapidOCR PP-OCRv6 small ONNX",
        "dpi": DPI,
        "note": "torch not imported in OCR worker to avoid onnxruntime CUDA slowdown",
    }
    write_json(GPU_INFO, info)
    return engine, info


def write_versions():
    from importlib.metadata import version
    import onnxruntime as ort
    import pymupdf

    def pkg_ver(name):
        try:
            return version(name)
        except Exception:
            return None

    write_json(VERSIONS, {
        "python": sys.version,
        "rapid_doc": pkg_ver("rapid-doc"),
        "torch": pkg_ver("torch"),
        "torchvision": pkg_ver("torchvision"),
        "onnxruntime": ort.__version__,
        "pymupdf": getattr(pymupdf, "VersionBind", None),
    })


def page_txt_path(file_dir, page_no):
    return file_dir / "page_text" / f"{page_no:04d}.txt"


def is_page_done(file_dir, page_no):
    return page_txt_path(file_dir, page_no).exists()


def append_page_record(file_dir, page_no, text, score_avg, elapse, error=None):
    pages_jsonl = file_dir / "pages.jsonl"
    record = {
        "page": page_no,
        "status": "ok" if error is None else "failed",
        "text": text,
        "score_avg": round(float(score_avg), 4) if score_avg is not None else None,
        "elapse": round(float(elapse), 3) if elapse is not None else None,
        "error": error,
    }
    with open(pages_jsonl, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def generate_docx(file_dir, total_pages, docx_path):
    from docx import Document
    doc = Document()
    for page_no in range(1, total_pages + 1):
        p = page_txt_path(file_dir, page_no)
        if p.exists():
            text = p.read_text(encoding="utf-8").strip()
        else:
            text = ""
        if text:
            doc.add_paragraph(text)
        if page_no < total_pages:
            doc.add_page_break()
    doc.save(docx_path)


def process_pdf(entry, ocr_engine, gpu_info, checkpoint, manifest_entries, manifest_map, progress_state, queue_total):
    import fitz  # pymupdf

    sha = entry["sha256"]
    fid = sha[:16]
    file_dir = FILES_DIR / fid
    file_dir.mkdir(parents=True, exist_ok=True)
    src = Path(entry["path"])

    meta_path = file_dir / "meta.json"
    if not meta_path.exists():
        write_json(meta_path, {
            "source_path": str(src),
            "filename": entry.get("filename"),
            "relative_scope": entry.get("relative_scope"),
            "sha256": sha,
            "queued_pages": entry.get("pages"),
            "output_root": str(OUT_ROOT),
            "created_at": now_str(),
        })

    if not src.exists():
        msg = f"source missing: {src}"
        log_error(msg)
        entry["status"] = "failed"
        entry["error"] = msg
        return False

    if not (file_dir / "sha256.checked").exists():
        actual_sha = sha256_of(src)
        if actual_sha != sha:
            msg = f"SHA-256 mismatch for {src}: expected {sha}, got {actual_sha}"
            log_error(msg)
            entry["status"] = "failed"
            entry["error"] = msg
            return False
        (file_dir / "sha256.checked").write_text(sha, encoding="utf-8")

    doc = fitz.open(str(src))
    total_pages = doc.page_count
    print(f"[{now_str()}] processing {entry.get('filename','')} pages={total_pages}", flush=True)
    progress_state["current_file"] = entry.get("filename")
    last_inner_report = time.time()

    cp = checkpoint.setdefault(sha, {"done": [], "failed": {}, "completed": False})
    done_set = set(cp.get("done", []))
    failed_map = cp.get("failed", {})
    # 以实际已生成的 page_text 为准，避免断点时 checkpoint 落后于文件
    page_text_dir = file_dir / "page_text"
    if page_text_dir.exists():
        for txt in page_text_dir.glob("*.txt"):
            try:
                n = int(txt.stem)
                if 1 <= n <= total_pages:
                    done_set.add(n)
            except ValueError:
                pass

    page_ok = 0
    page_fail = 0
    for page_no in range(1, total_pages + 1):
        if page_no in done_set:
            page_ok += 1
            continue
        tmp_img = file_dir / "_tmp_page.png"
        try:
            t_render = time.time()
            pix = doc.load_page(page_no - 1).get_pixmap(dpi=DPI)
            pix.save(str(tmp_img))
            dt_render = time.time() - t_render
            t0 = time.time()
            res = ocr_engine(str(tmp_img))
            elapse = time.time() - t0
            if res.txts is not None and len(res.txts) > 0:
                text = "\n".join(res.txts)
                score_avg = sum(res.scores) / len(res.scores)
            else:
                text = ""
                score_avg = 0.0
            t_write = time.time()
            page_txt_path(file_dir, page_no).parent.mkdir(parents=True, exist_ok=True)
            page_txt_path(file_dir, page_no).write_text(text, encoding="utf-8")
            append_page_record(file_dir, page_no, text, score_avg, elapse)
            dt_write = time.time() - t_write
            done_set.add(page_no)
            page_ok += 1
            if os.environ.get("OCR_DEBUG"):
                print(f"  page {page_no}: render={dt_render:.2f}s ocr={elapse:.2f}s write={dt_write:.2f}s", flush=True)
        except Exception as e:
            page_fail += 1
            failed_map[str(page_no)] = str(e)
            append_page_record(file_dir, page_no, "", None, None, error=str(e))
            log_error(f"{entry.get('filename')} page {page_no}: {e}\n{traceback.format_exc()}")
        finally:
            try:
                tmp_img.unlink(missing_ok=True)
            except Exception:
                pass
        if (page_ok + page_fail) % 5 == 0:
            cp["done"] = sorted(done_set)
            cp["failed"] = failed_map
            save_checkpoint(checkpoint)
        progress_state["done_pages"] += 1
        progress_state["failed_pages"] += (1 if str(page_no) in failed_map else 0)

        # 文件内定时/定量写进度报告
        if time.time() - last_inner_report >= PROGRESS_INTERVAL or (page_ok + page_fail) % 50 == 0:
            write_progress_report(progress_state, gpu_info, queue_total, manifest_map)
            last_inner_report = time.time()

    doc.close()
    cp["done"] = sorted(done_set)
    cp["failed"] = failed_map
    cp["completed"] = page_fail == 0
    save_checkpoint(checkpoint)

    docx_path = file_dir / "output.docx"
    try:
        generate_docx(file_dir, total_pages, docx_path)
        entry["docx_path"] = str(docx_path)
    except Exception as e:
        log_error(f"docx generation failed for {entry.get('filename')}: {e}\n{traceback.format_exc()}")
        entry["error"] = f"docx: {e}"

    entry["status"] = "completed" if page_fail == 0 else "completed_with_errors"
    entry["completed_pages"] = page_ok
    entry["failed_pages"] = page_fail
    entry["total_pages"] = total_pages
    entry["output_dir"] = str(file_dir)
    entry["error"] = entry.get("error")
    entry["gpu_provider"] = gpu_info.get("ocr_actual_providers", [])
    return page_fail == 0


def write_progress_report(progress_state, gpu_info, queue_total, manifest_map):
    obj = {
        "timestamp": now_str(),
        "total_pdfs": queue_total,
        "completed_pdfs": progress_state["completed_pdfs"],
        "failed_pdfs": progress_state["failed_pdfs"],
        "done_pages": progress_state["done_pages"],
        "failed_pages": progress_state["failed_pages"],
        "current_file": progress_state["current_file"],
        "gpu": gpu_info,
        "output_root": str(OUT_ROOT),
        "pending_review": [],
    }
    path = PROGRESS_DIR / f"progress_{datetime.now(CST).strftime('%Y%m%d_%H%M%S')}.json"
    write_json(path, obj)
    write_json(PROGRESS_DIR / "latest_progress.json", obj)
    return obj


def main():
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    write_versions()

    queue = load_queue()
    manifest_map = load_manifest()
    checkpoint = load_checkpoint()

    manifest_entries = []
    for row in queue:
        old = manifest_map.get(row["sha256"])
        if old:
            merged = dict(row)
            merged.update({k: v for k, v in old.items() if k not in ("filename", "path", "pages", "sha256")})
            manifest_entries.append(merged)
        else:
            manifest_entries.append(dict(row))

    ocr_engine, gpu_info = build_ocr_engine()
    print(f"[{now_str()}] GPU info: {json.dumps(gpu_info, ensure_ascii=False)}", flush=True)

    progress_state = {
        "completed_pdfs": sum(1 for e in manifest_entries if e.get("status") in ("completed", "completed_with_errors")),
        "failed_pdfs": sum(1 for e in manifest_entries if e.get("status") == "failed"),
        "done_pages": 0,
        "failed_pages": 0,
        "current_file": None,
    }
    for sha, cp in checkpoint.items():
        progress_state["done_pages"] += len(cp.get("done", []))
        progress_state["failed_pages"] += len(cp.get("failed", {}))

    queue_total = len(queue)
    last_report = time.time()
    write_progress_report(progress_state, gpu_info, queue_total, manifest_map)

    for idx, entry in enumerate(manifest_entries, 1):
        if entry.get("status") in ("completed", "completed_with_errors"):
            print(f"[{now_str()}] skip completed {idx}/{queue_total}: {entry.get('filename','')}", flush=True)
            continue
        if entry.get("status") == "failed":
            print(f"[{now_str()}] skip failed {idx}/{queue_total}: {entry.get('filename','')}", flush=True)
            continue
        print(f"[{now_str()}] [{idx}/{queue_total}] start {entry.get('filename','')}", flush=True)
        try:
            ok = process_pdf(entry, ocr_engine, gpu_info, checkpoint, manifest_entries, manifest_map, progress_state, queue_total)
            if ok:
                progress_state["completed_pdfs"] += 1
            else:
                progress_state["failed_pdfs"] += 1
        except Exception as e:
            log_error(f"file failed {entry.get('filename')}: {e}\n{traceback.format_exc()}")
            entry["status"] = "failed"
            entry["error"] = str(e)
            progress_state["failed_pdfs"] += 1
        save_manifest(manifest_entries)
        save_checkpoint(checkpoint)
        write_progress_report(progress_state, gpu_info, queue_total, manifest_map)

        if time.time() - last_report >= PROGRESS_INTERVAL:
            write_progress_report(progress_state, gpu_info, queue_total, manifest_map)
            last_report = time.time()

    save_manifest(manifest_entries)
    save_checkpoint(checkpoint)
    final = write_progress_report(progress_state, gpu_info, queue_total, manifest_map)
    print(f"[{now_str()}] ALL DONE {json.dumps(final, ensure_ascii=False)}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("interrupted", flush=True)
    except Exception:
        log_error("FATAL\n" + traceback.format_exc())
        raise
