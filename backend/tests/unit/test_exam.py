def test_exam_overview_reports_materials(client):
    response = client.get("/api/exam/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["material_count"] == 12
    assert data["ocr_pending"] == 4
    assert [track["points"] for track in data["tracks"]] == [150, 150]


def test_bootstrap_is_idempotent(client):
    first = client.post("/api/exam/bootstrap")
    second = client.post("/api/exam/bootstrap")

    assert first.status_code == 200
    assert first.json()["created"] is True
    assert second.json() == {"course_id": first.json()["course_id"], "created": False}

    course = client.get(f"/api/courses/{first.json()['course_id']}").json()
    assert course["lesson_count"] == 1
    assert "中国历史 · 150分" in course["syllabus_content"]


def test_anki_export_is_utf8_tsv(client):
    response = client.get("/api/exam/anki.tsv")

    assert response.status_code == 200
    text = response.content.decode("utf-8-sig")
    assert text.startswith("Front\tBack\tTags\n")
    assert "史料判读" in text
