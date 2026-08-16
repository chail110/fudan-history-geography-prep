#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crosscheck: 中国历史政治地理十六讲（下载版） vs 已有版
- 等待当前 40-PDF worker 结束后自动执行
- 使用相同 GPU OCR 管线
- 输出到 crosscheck/中国历史政治地理十六讲_下载版
"""
import importlib.util
import json
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta

HARNESS = Path(r"D:\workspace\历史地理\ocr\deepseek-harness\run_ocr_queue.py")
OUT_ROOT = Path(r"D:\workspace\历史地理\ocr\deepseek-harness")
CROSS_DIR = OUT_ROOT / "crosscheck" / "中国历史政治地理十六讲_下载版"
EXISTING_DIR = OUT_ROOT / "files" / "a316282dd770c3c6"
NEW_PDF = Path(r"C:\Users\30374\Downloads\中国历史政治地理十六讲 (周振鹤) (z-library.sk, 1lib.sk, z-lib.sk).pdf")
MANIFEST = OUT_ROOT / "manifest.jsonl"
DPI = 200
CST = timezone(timedelta(hours=8))


def now_str():
    return datetime.now(CST).isoformat(timespec="seconds")


def log(msg):
    line = f"[{now_str()}] {msg}"
    print(line, flush=True)
    CROSS_DIR.mkdir(parents=True, exist_ok=True)
    with open(CROSS_DIR / "crosscheck_error.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_harness():
    spec = importlib.util.spec_from_file_location("harness", HARNESS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def worker_done():
    if MANIFEST.exists():
        with open(MANIFEST, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
        if len(rows) >= 40 and all(r.get("status") in ("completed", "completed_with_errors", "failed") for r in rows):
            return True
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=20
        ).stdout or ""
        return "run_ocr_queue.py" not in out
    except Exception:
        return False


def wait_for_worker():
    log("Waiting for current 40-PDF worker to finish before crosscheck OCR...")
    while not worker_done():
        time.sleep(30)
    log("Current worker appears finished. Starting crosscheck.")


def ocr_new_pdf(mod):
    ocr_engine, gpu_info = mod.build_ocr_engine()
    log("GPU info: " + json.dumps(gpu_info, ensure_ascii=False))
    (CROSS_DIR / "gpu_info.json").write_text(json.dumps(gpu_info, ensure_ascii=False, indent=2), encoding="utf-8")

    import pymupdf
    doc = pymupdf.open(str(NEW_PDF))
    total = doc.page_count
    page_text_dir = CROSS_DIR / "page_text"
    page_text_dir.mkdir(parents=True, exist_ok=True)
    pages_jsonl = CROSS_DIR / "pages.jsonl"
    cp_path = CROSS_DIR / "checkpoint.json"
    cp = {"sha256": None, "done": [], "failed": {}}
    if cp_path.exists():
        cp = json.loads(cp_path.read_text(encoding="utf-8"))
    done = set(cp.get("done", []))

    for page_no in range(1, total + 1):
        if page_no in done:
            continue
        tmp = CROSS_DIR / "_tmp_page.png"
        try:
            pix = doc.load_page(page_no - 1).get_pixmap(dpi=DPI)
            pix.save(str(tmp))
            t0 = time.time()
            res = ocr_engine(str(tmp))
            elapse = time.time() - t0
            if res.txts is not None and len(res.txts) > 0:
                text = "\n".join(res.txts)
                score = sum(res.scores) / len(res.scores)
            else:
                text = ""
                score = 0.0
            (page_text_dir / f"{page_no:04d}.txt").write_text(text, encoding="utf-8")
            with open(pages_jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "page": page_no,
                    "status": "ok",
                    "text": text,
                    "score_avg": round(score, 4),
                    "elapse": round(elapse, 3),
                    "error": None,
                }, ensure_ascii=False) + "\n")
            done.add(page_no)
        except Exception as e:
            cp["failed"][str(page_no)] = str(e)
            with open(pages_jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps({"page": page_no, "status": "failed", "text": "", "score_avg": None, "elapse": None, "error": str(e)}, ensure_ascii=False) + "\n")
            log(f"page {page_no} failed: {e}\n{traceback.format_exc()}")
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        cp["done"] = sorted(done)
        cp_path.write_text(json.dumps(cp, ensure_ascii=False, indent=2), encoding="utf-8")

    doc.close()

    from docx import Document
    d = Document()
    for page_no in range(1, total + 1):
        p = page_text_dir / f"{page_no:04d}.txt"
        text = p.read_text(encoding="utf-8").strip() if p.exists() else ""
        if text:
            d.add_paragraph(text)
        if page_no < total:
            d.add_page_break()
    d.save(CROSS_DIR / "output.docx")

    meta = json.loads((CROSS_DIR / "source_meta.json").read_text(encoding="utf-8"))
    manifest = {
        "source_path": str(NEW_PDF),
        "filename": NEW_PDF.name,
        "sha256": meta["sha256"],
        "size_bytes": meta["size_bytes"],
        "actual_pages": total,
        "status": "completed" if not cp["failed"] else "completed_with_errors",
        "output_dir": str(CROSS_DIR),
        "docx_path": str(CROSS_DIR / "output.docx"),
        "gpu_provider": gpu_info.get("ocr_actual_providers", []),
        "completed_at": now_str(),
    }
    (CROSS_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta, gpu_info


def norm_text(s):
    return re.sub(r"\s+", "", s or "")


def ratio(a, b):
    import difflib
    return difflib.SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()


def extract_titles(text):
    titles = []
    for line in (text or "").splitlines():
        line = line.strip()
        if re.search(r"第[一二三四五六七八九十百0-9]+讲", line) and len(line) <= 60:
            titles.append(line)
    return titles


def load_pages(dirpath):
    pt = Path(dirpath) / "page_text"
    pages = {}
    if pt.exists():
        for txt in sorted(pt.glob("*.txt")):
            pages[int(txt.stem)] = txt.read_text(encoding="utf-8").strip()
    return pages


def load_jsonl_scores(dirpath):
    scores = {}
    p = Path(dirpath) / "pages.jsonl"
    if p.exists():
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            scores[int(r["page"])] = r.get("score_avg")
    return scores


def compare(old_pages, new_pages, old_scores, new_scores):
    best_shift = 0
    best_score = -1.0
    for shift in range(-10, 11):
        vals = []
        for np_ in new_pages:
            op = np_ + shift
            if op in old_pages:
                vals.append(ratio(old_pages[op], new_pages[np_]))
        if vals:
            avg = sum(vals) / len(vals)
            if avg > best_score:
                best_score = avg
                best_shift = shift

    rows = []
    all_pages = sorted(set(old_pages.keys()) | set(new_pages.keys()))
    for p in all_pages:
        op = p - best_shift
        old_text = old_pages.get(op, "")
        new_text = new_pages.get(p, "")
        r = ratio(old_text, new_text) if (old_text or new_text) else 1.0
        old_empty = not old_text.strip()
        new_empty = not new_text.strip()
        old_score = old_scores.get(op)
        new_score = new_scores.get(p)
        low_conf = (old_score is not None and old_score < 0.8) or (new_score is not None and new_score < 0.8)
        if old_empty and new_empty:
            verdict = "同版本"
        elif r >= 0.95:
            verdict = "同版本"
        elif r >= 0.70:
            verdict = "不同扫描版"
        elif old_empty != new_empty:
            verdict = "无法对齐"
        else:
            verdict = "内容差异"
        rows.append({
            "new_page": p,
            "aligned_old_page": op,
            "shift": best_shift,
            "similarity": round(r, 4),
            "old_empty": old_empty,
            "new_empty": new_empty,
            "old_score_avg": round(old_score, 4) if old_score is not None else None,
            "new_score_avg": round(new_score, 4) if new_score is not None else None,
            "low_confidence": low_conf,
            "old_titles": extract_titles(old_text),
            "new_titles": extract_titles(new_text),
            "verdict": verdict,
        })
    return rows, best_shift, best_score


def write_reports(meta, gpu_info, rows, best_shift, best_score):
    from collections import Counter
    cnt = Counter(r["verdict"] for r in rows)
    report = {
        "generated_at": now_str(),
        "source": meta,
        "existing_dir": str(EXISTING_DIR),
        "new_dir": str(CROSS_DIR),
        "existing_pages": len({r["aligned_old_page"] for r in rows if r["aligned_old_page"] is not None}),
        "new_pages": len({r["new_page"] for r in rows}),
        "best_shift": best_shift,
        "best_avg_similarity": round(best_score, 4),
        "verdict_counts": dict(cnt),
        "gpu": gpu_info,
        "manual_review_pages": [r for r in rows if r["verdict"] in ("内容差异", "无法对齐") or r["low_confidence"]],
    }
    (CROSS_DIR / "comparison_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(CROSS_DIR / "page_diffs.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    md = []
    md.append("# 中国历史政治地理十六讲 版本对比报告")
    md.append("")
    md.append(f"- 生成时间：{now_str()}")
    md.append(f"- 新下载版：{NEW_PDF.name}")
    md.append(f"- 新下载版 SHA-256：{meta['sha256']}")
    md.append(f"- 已有版目录：{EXISTING_DIR}")
    md.append(f"- 已有版页数：{len({r['aligned_old_page'] for r in rows if r['aligned_old_page'] is not None})}")
    md.append(f"- 新下载版页数：{len({r['new_page'] for r in rows})}")
    md.append(f"- 最佳页码偏移：{best_shift}")
    md.append(f"- 最佳平均文本相似度：{round(best_score, 4)}")
    md.append("")
    md.append("## 判定统计")
    for k, v in cnt.items():
        md.append(f"- {k}: {v}")
    md.append("")
    md.append("## 人工复核清单")
    review = report["manual_review_pages"]
    if review:
        for r in review:
            md.append(f"- 新页 {r['new_page']} ↔ 旧页 {r['aligned_old_page']}：{r['verdict']}，相似度 {r['similarity']}，低置信度={r['low_confidence']}")
    else:
        md.append("- 无")
    md.append("")
    (CROSS_DIR / "comparison_report.md").write_text("\n".join(md), encoding="utf-8")
    log(f"comparison report written: {CROSS_DIR / 'comparison_report.md'}")


def main():
    CROSS_DIR.mkdir(parents=True, exist_ok=True)
    wait_for_worker()
    mod = load_harness()
    meta, gpu_info = ocr_new_pdf(mod)
    old_pages = load_pages(EXISTING_DIR)
    new_pages = load_pages(CROSS_DIR)
    old_scores = load_jsonl_scores(EXISTING_DIR)
    new_scores = load_jsonl_scores(CROSS_DIR)
    rows, best_shift, best_score = compare(old_pages, new_pages, old_scores, new_scores)
    write_reports(meta, gpu_info, rows, best_shift, best_score)
    log("CROSSCHECK DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("FATAL\n" + traceback.format_exc())
        raise
