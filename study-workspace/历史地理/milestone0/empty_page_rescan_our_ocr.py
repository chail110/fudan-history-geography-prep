#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# noqa: SIZE_OK — one-shot, single-purpose rescan runner; it is not a reusable application layer.
"""独立复扫 DSH 标记为空的 PDF 页面。

只读取 DSH 的 manifest/source_meta 和原 PDF，使用本地 RapidOCR PP-OCRv6
在 300 DPI 下重新渲染。结果写入独立目录，不覆盖 DSH 原始输出，也不写入
Universal ExamPrep。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_source(recorded: Path, expected_sha: str | None) -> Path:
    """Resolve a source path even if an earlier JSON writer mangled Unicode names."""
    if recorded.exists():
        return recorded
    candidates = []
    if recorded.parent.exists():
        candidates.extend(recorded.parent.glob("*.pdf"))
    candidates.extend(Path(r"C:\Users\30374\Downloads").glob("*.pdf"))
    candidates.extend(Path(r"C:\Users\30374\Desktop\历史地理").glob("*.pdf"))
    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        if expected_sha and sha256(candidate) == expected_sha:
            return candidate
    return recorded


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def empty_pages_for_dir(path: Path) -> list[int]:
    page_dir = path / "page_text"
    pages = []
    if not page_dir.exists():
        return pages
    for txt in sorted(page_dir.glob("*.txt")):
        if not txt.read_text(encoding="utf-8").strip():
            try:
                pages.append(int(txt.stem))
            except ValueError:
                pass
    return pages


def build_targets(root: Path, include_crosscheck: bool):
    targets = []
    for line in (root / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out_dir = Path(row["output_dir"])
        pages = empty_pages_for_dir(out_dir)
        if pages:
            targets.append(
                {
                    "kind": "main",
                    "filename": row.get("filename"),
                    "source_path": row["path"],
                    "sha256": row.get("sha256"),
                    "output_dir": str(out_dir),
                    "pages": pages,
                }
            )

    if include_crosscheck:
        for meta_path in (root / "crosscheck").glob("*/source_meta.json"):
            meta = load_json(meta_path)
            out_dir = meta_path.parent
            pages = empty_pages_for_dir(out_dir)
            if pages:
                targets.append(
                    {
                        "kind": "crosscheck",
                        "filename": meta.get("filename") or Path(meta["source_path"]).name,
                        "source_path": meta["source_path"],
                        "sha256": meta.get("sha256"),
                        "output_dir": str(out_dir),
                        "pages": pages,
                    }
                )
    return targets


def build_engine(resources: Path):
    import onnxruntime as ort
    from rapidocr import RapidOCR, EngineType, OCRVersion, ModelType

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
    if "CUDAExecutionProvider" in ort.get_available_providers():
        params["EngineConfig.onnxruntime.use_cuda"] = True
        params["EngineConfig.onnxruntime.cuda_ep_cfg.device_id"] = 0
    engine = RapidOCR(params=params)
    providers = []
    try:
        providers = engine.text_det.session.session.get_providers()
    except Exception:
        pass
    return engine, {
        "engine": "RapidOCR PP-OCRv6 small ONNX (independent rescan)",
        "dpi": 300,
        "available_providers": ort.get_available_providers(),
        "actual_providers": providers,
        "preprocess": "300dpi RGB; retry with grayscale autocontrast and 1.5x upscale if first pass is empty/low-confidence",
    }


def run_page(engine, doc, page_no: int, tmp_png: Path):
    from PIL import Image, ImageOps
    # 输入来自本地备考资料；部分超大幅扫描页超过 Pillow 默认安全阈值。
    # 这里不接受外部不可信图片，只对已校验 SHA-256 的本地 PDF 解码。
    Image.MAX_IMAGE_PIXELS = None

    page = doc.load_page(page_no - 1)
    pix = page.get_pixmap(dpi=300, alpha=False)
    pix.save(str(tmp_png))
    variants = [("rgb_300dpi", tmp_png)]

    def call(path):
        result = engine(str(path))
        if result.txts is None or len(result.txts) == 0:
            return "", 0.0, 0
        text = "\n".join(str(t) for t in result.txts).strip()
        scores = [float(s) for s in result.scores] if result.scores is not None else []
        return text, (sum(scores) / len(scores) if scores else 0.0), len(result.txts)

    best = None
    for variant, path in variants:
        text, score, count = call(path)
        best = (text, score, count, variant)
        if text and score >= 0.90:
            return best

    with Image.open(tmp_png) as im:
        gray = ImageOps.autocontrast(ImageOps.grayscale(im))
        up = gray.resize((int(gray.width * 1.5), int(gray.height * 1.5)))
        retry = tmp_png.with_name(tmp_png.stem + "_retry.png")
        up.save(retry)
    try:
        text, score, count = call(retry)
        candidate = (text, score, count, "gray_autocontrast_450dpi_equiv")
        if best is None or (candidate[0] and (not best[0] or candidate[1] > best[1])):
            best = candidate
    finally:
        retry.unlink(missing_ok=True)
    return best or ("", 0.0, 0, "none")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--resources", type=Path, default=Path(r"D:\workspace\ocr-venv\Lib\site-packages\rapid_doc\resources"))
    ap.add_argument("--include-crosscheck", action="store_true")
    ap.add_argument("--only-errors-from", type=Path, default=None)
    args = ap.parse_args()

    import fitz

    targets = build_targets(args.root, args.include_crosscheck)
    if args.only_errors_from:
        previous = []
        for line in args.only_errors_from.read_text(encoding="utf-8").splitlines():
            if line.strip():
                previous.append(json.loads(line))
        wanted = {
            (r.get("kind"), r.get("sha256"), int(r["page"]))
            for r in previous
            if r.get("status") != "ok"
        }
        for target in targets:
            target["pages"] = [
                p for p in target["pages"]
                if (target["kind"], target.get("sha256"), p) in wanted
            ]
        targets = [t for t in targets if t["pages"]]
    total = sum(len(t["pages"]) for t in targets)
    args.out.mkdir(parents=True, exist_ok=True)
    engine, engine_info = build_engine(args.resources)
    run_meta = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "method": "independent_local_rapidocr_rescan",
        "target_policy": "all DSH page_text files whose stripped text is empty",
        "include_crosscheck": args.include_crosscheck,
        "target_books": len(targets),
        "target_pages": total,
        "engine": engine_info,
        "source_outputs_unchanged": True,
        "formal_universal_exam_prep_ingest": False,
    }
    (args.out / "run_meta.json").write_text(json.dumps(run_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "targets.json").write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8")

    all_records = []
    done = 0
    for target in targets:
        recorded_source = Path(target["source_path"])
        source = resolve_source(recorded_source, target.get("sha256"))
        rec_dir = args.out / target["sha256"][:16]
        rec_dir.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            for page_no in target["pages"]:
                all_records.append({**target, "page": page_no, "status": "source_missing", "text": ""})
            continue
        actual_sha = sha256(source)
        if target.get("sha256") and actual_sha != target["sha256"]:
            for page_no in target["pages"]:
                all_records.append({**target, "page": page_no, "status": "sha256_mismatch", "actual_sha256": actual_sha, "text": ""})
            continue
        doc = fitz.open(str(source))
        tmp_dir = Path(tempfile.mkdtemp(prefix="ocr_rescan_", dir=str(args.out)))
        try:
            for page_no in target["pages"]:
                tmp_png = tmp_dir / f"page_{page_no:04d}.png"
                started = time.time()
                try:
                    text, score, count, variant = run_page(engine, doc, page_no, tmp_png)
                    status = "ok"
                except Exception as exc:
                    text, score, count, variant = "", None, 0, "error"
                    status = "error"
                    error = repr(exc)
                else:
                    error = None
                (rec_dir / f"page_{page_no:04d}.txt").write_text(text, encoding="utf-8")
                record = {
                    "kind": target["kind"],
                    "filename": target["filename"],
                    "source_path": str(source),
                    "recorded_source_path": str(recorded_source),
                    "sha256": target.get("sha256"),
                    "page": page_no,
                    "status": status,
                    "text": text,
                    "text_chars": len(text),
                    "score_avg": round(score, 4) if score is not None else None,
                    "detections": count,
                    "variant": variant,
                    "elapsed_seconds": round(time.time() - started, 3),
                    "error": error,
                }
                all_records.append(record)
                done += 1
                print(f"[{done}/{total}] {target['filename']} page={page_no} chars={len(text)} score={score} variant={variant}", flush=True)
        finally:
            doc.close()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    with (args.out / "results.jsonl").open("w", encoding="utf-8") as f:
        for row in all_records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = {
        "target_books": len(targets),
        "target_pages": total,
        "rescanned": len(all_records),
        "nonempty_after_rescan": sum(bool(r.get("text", "").strip()) for r in all_records),
        "still_empty_after_rescan": sum(not r.get("text", "").strip() for r in all_records),
        "errors": sum(r.get("status") != "ok" for r in all_records),
        "low_score_nonempty_lt_0_90": sum(bool(r.get("text", "").strip()) and isinstance(r.get("score_avg"), (int, float)) and r["score_avg"] < 0.90 for r in all_records),
    }
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
