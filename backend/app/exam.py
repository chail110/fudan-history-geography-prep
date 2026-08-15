import csv
import io
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.exam_catalog import (
    ANKI_CARDS,
    COURSE_NAME,
    DIAGNOSTIC_LESSON,
    EXAM_DATE,
    EXAM_NAME,
    SYLLABUS,
    material_catalog,
)
from app.models import Course, LearningEvent, Lesson, Syllabus

router = APIRouter(prefix="/api/exam", tags=["exam"])


def _days_remaining() -> int:
    return max((date.fromisoformat(EXAM_DATE) - datetime.now(UTC).date()).days, 0)


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.name == COURSE_NAME).first()
    materials = material_catalog(settings.MATERIALS_DIR)
    return {
        "exam_name": EXAM_NAME,
        "exam_date": EXAM_DATE,
        "exam_date_is_estimate": True,
        "days_remaining": _days_remaining(),
        "course_id": course.id if course else None,
        "material_count": len(materials),
        "material_ready": sum(item["available"] for item in materials),
        "ocr_pending": sum(item["processing"] == "ocr" for item in materials),
        "tracks": [
            {"name": "历史地理学专业知识", "points": 150, "required": True},
            {"name": "中国历史", "points": 150, "required": True},
        ],
        "today": ["完成诊断题", "建立第一批名词解释卡", "订正一道真题答案"],
    }


@router.get("/materials")
def materials():
    return {"root": settings.MATERIALS_DIR, "items": material_catalog(settings.MATERIALS_DIR)}


@router.post("/bootstrap")
def bootstrap(db: Session = Depends(get_db)):
    existing = db.query(Course).filter(Course.name == COURSE_NAME).first()
    if existing:
        return {"course_id": existing.id, "created": False}

    course = Course(name=COURSE_NAME, mode="topic", learning_depth="deep")
    db.add(course)
    db.flush()
    db.add(Syllabus(course_id=course.id, content=SYLLABUS))
    db.add(Lesson(course_id=course.id, number=1, content=DIAGNOSTIC_LESSON))
    db.add(LearningEvent(course_id=course.id, lesson_number=1, event_type="exam_course_created"))
    db.commit()
    return {"course_id": course.id, "created": True}


@router.get("/anki.tsv")
def anki_export():
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(("Front", "Back", "Tags"))
    writer.writerows(ANKI_CARDS)
    content = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([content]),
        media_type="text/tab-separated-values; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="history-geography-anki.tsv"'},
    )
