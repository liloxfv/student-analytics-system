import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


STUDENT = {"student_code": "S1", "first_name": "سارا", "last_name": "احمدی", "grade_level": "دهم", "class_name": "۱۰-الف"}
TODAY = date.today().isoformat()


def make_student(client, **over):
    return client.post("/api/students", json={**STUDENT, **over}).json()


def test_create_and_list_student(client):
    assert client.post("/api/students", json=STUDENT).status_code == 201
    assert client.get("/api/students").json()[0]["student_code"] == "S1"


def test_duplicate_student_code_is_rejected(client):
    make_student(client)
    assert client.post("/api/students", json=STUDENT).status_code == 409


def test_unknown_student_returns_404(client):
    assert client.get("/api/students/999").status_code == 404


def test_grade_out_of_range_is_rejected(client):
    s = make_student(client)
    subj = client.post("/api/subjects", json={"name": "ریاضی"}).json()
    body = {"student_id": s["id"], "subject_id": subj["id"], "exam_date": TODAY}
    assert client.post("/api/grades", json={**body, "score": 21}).status_code == 422
    assert client.post("/api/grades", json={**body, "score": -1}).status_code == 422
    assert client.post("/api/grades", json={**body, "score": 20}).status_code == 201


def test_grade_requires_existing_student(client):
    subj = client.post("/api/subjects", json={"name": "ریاضی"}).json()
    r = client.post("/api/grades", json={"student_id": 99, "subject_id": subj["id"], "score": 15, "exam_date": TODAY})
    assert r.status_code == 404


def test_attendance_is_upserted_not_duplicated(client):
    s = make_student(client)
    body = {"day": TODAY, "records": [{"student_id": s["id"], "status": "present"}]}
    assert client.post("/api/attendance", json=body).status_code == 200
    body["records"][0]["status"] = "absent"
    assert client.post("/api/attendance", json=body).status_code == 200
    rows = client.get("/api/attendance", params={"day": TODAY}).json()
    assert len(rows) == 1 and rows[0]["status"] == "absent"


def test_summary_on_empty_database_has_no_fake_averages(client):
    data = client.get("/api/analytics/summary").json()
    assert data["students"] == 0
    assert data["average"] is None
    assert data["attendance"]["rate"] is None


def test_report_detects_trend_and_needs_enough_data(client):
    s = make_student(client)
    subj = client.post("/api/subjects", json={"name": "ریاضی"}).json()
    for i, score in enumerate([8, 10, 12, 14]):
        client.post("/api/grades", json={"student_id": s["id"], "subject_id": subj["id"], "score": score, "exam_date": f"2026-01-{i + 1:02d}"})
    report = client.get(f"/api/students/{s['id']}/report").json()
    assert report["subjects"][0]["direction"] == "up"
    assert report["average"] == 11.0

    s2 = make_student(client, student_code="S2")
    client.post("/api/grades", json={"student_id": s2["id"], "subject_id": subj["id"], "score": 15, "exam_date": TODAY})
    assert client.get(f"/api/students/{s2['id']}/report").json()["subjects"][0]["direction"] == "insufficient"


def test_deleting_student_removes_their_grades(client):
    s = make_student(client)
    subj = client.post("/api/subjects", json={"name": "ریاضی"}).json()
    client.post("/api/grades", json={"student_id": s["id"], "subject_id": subj["id"], "score": 15, "exam_date": TODAY})
    assert client.delete(f"/api/students/{s['id']}").status_code == 204
    assert client.get("/api/grades").json() == []
