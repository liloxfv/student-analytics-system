from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from . import analytics
from .database import engine, get_db
from .models import Attendance, Base, Grade, Student, Subject
from .schemas import (
    AttendanceBulk,
    AttendanceOut,
    GradeIn,
    GradeOut,
    StudentIn,
    StudentOut,
    SubjectIn,
    SubjectOut,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Student Analytics System", version="1.0.0", lifespan=lifespan)


def get_student_or_404(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "دانش‌آموز پیدا نشد.")
    return student


def student_out(student: Student, average: float | None = None) -> StudentOut:
    out = StudentOut.model_validate(student)
    out.average = None if average is None else round(float(average), 2)
    return out


def grade_out(g: Grade) -> GradeOut:
    return GradeOut(
        id=g.id,
        student_id=g.student_id,
        student_name=g.student.full_name,
        subject_id=g.subject_id,
        subject_name=g.subject.name,
        score=g.score,
        exam_date=g.exam_date,
        title=g.title,
    )


# ---------- Students ----------
@app.get("/api/students", response_model=list[StudentOut])
def list_students(
    search: str | None = None,
    class_name: str | None = None,
    sort: Literal["name", "class", "average"] = "name",
    db: Session = Depends(get_db),
):
    avg = select(Grade.student_id, func.avg(Grade.score).label("avg")).group_by(Grade.student_id).subquery()
    q = select(Student, avg.c.avg).outerjoin(avg, avg.c.student_id == Student.id)
    if search and search.strip():
        like = f"%{search.strip()}%"
        q = q.where(or_(Student.first_name.like(like), Student.last_name.like(like), Student.student_code.like(like)))
    if class_name:
        q = q.where(Student.class_name == class_name)
    rows = [student_out(s, a) for s, a in db.execute(q).all()]
    if sort == "average":
        rows.sort(key=lambda s: (s.average is None, -(s.average or 0)))
    elif sort == "class":
        rows.sort(key=lambda s: (s.class_name, s.last_name, s.first_name))
    else:
        rows.sort(key=lambda s: (s.last_name, s.first_name))
    return rows


@app.post("/api/students", response_model=StudentOut, status_code=201)
def create_student(data: StudentIn, db: Session = Depends(get_db)):
    student = Student(**data.model_dump())
    db.add(student)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "این کد دانش‌آموزی قبلاً ثبت شده است.")
    return student_out(student)


@app.get("/api/students/{student_id}", response_model=StudentOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    return student_out(get_student_or_404(db, student_id))


@app.put("/api/students/{student_id}", response_model=StudentOut)
def update_student(student_id: int, data: StudentIn, db: Session = Depends(get_db)):
    student = get_student_or_404(db, student_id)
    for key, value in data.model_dump().items():
        setattr(student, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "این کد دانش‌آموزی قبلاً ثبت شده است.")
    return student_out(student)


@app.delete("/api/students/{student_id}", status_code=204)
def delete_student(student_id: int, db: Session = Depends(get_db)):
    db.delete(get_student_or_404(db, student_id))
    db.commit()
    return Response(status_code=204)


@app.get("/api/students/{student_id}/report")
def student_report(student_id: int, db: Session = Depends(get_db)):
    return analytics.student_report(db, get_student_or_404(db, student_id))


# ---------- Subjects ----------
@app.get("/api/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db)):
    return db.scalars(select(Subject).order_by(Subject.name)).all()


@app.post("/api/subjects", response_model=SubjectOut, status_code=201)
def create_subject(data: SubjectIn, db: Session = Depends(get_db)):
    subject = Subject(name=data.name)
    db.add(subject)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "این درس قبلاً ثبت شده است.")
    return subject


# ---------- Grades ----------
@app.get("/api/grades", response_model=list[GradeOut])
def list_grades(
    student_id: int | None = None,
    subject_id: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = select(Grade).options(selectinload(Grade.student), selectinload(Grade.subject))
    if student_id:
        q = q.where(Grade.student_id == student_id)
    if subject_id:
        q = q.where(Grade.subject_id == subject_id)
    q = q.order_by(Grade.exam_date.desc(), Grade.id.desc()).limit(limit)
    return [grade_out(g) for g in db.scalars(q).all()]


@app.post("/api/grades", response_model=GradeOut, status_code=201)
def create_grade(data: GradeIn, db: Session = Depends(get_db)):
    get_student_or_404(db, data.student_id)
    if not db.get(Subject, data.subject_id):
        raise HTTPException(404, "درس پیدا نشد.")
    grade = Grade(**data.model_dump())
    db.add(grade)
    db.commit()
    db.refresh(grade)
    return grade_out(grade)


@app.delete("/api/grades/{grade_id}", status_code=204)
def delete_grade(grade_id: int, db: Session = Depends(get_db)):
    grade = db.get(Grade, grade_id)
    if not grade:
        raise HTTPException(404, "نمره پیدا نشد.")
    db.delete(grade)
    db.commit()
    return Response(status_code=204)


# ---------- Attendance ----------
@app.get("/api/attendance", response_model=list[AttendanceOut])
def list_attendance(
    day: date | None = None,
    class_name: str | None = None,
    student_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = select(Attendance).join(Student).options(selectinload(Attendance.student))
    if day:
        q = q.where(Attendance.day == day)
    if class_name:
        q = q.where(Student.class_name == class_name)
    if student_id:
        q = q.where(Attendance.student_id == student_id)
    rows = db.scalars(q.order_by(Attendance.day.desc(), Student.last_name).limit(2000)).all()
    return [
        AttendanceOut(student_id=a.student_id, student_name=a.student.full_name, class_name=a.student.class_name, day=a.day, status=a.status)
        for a in rows
    ]


@app.post("/api/attendance")
def save_attendance(data: AttendanceBulk, db: Session = Depends(get_db)):
    """Create or update one record per student for the given day (never duplicates)."""
    wanted = {r.student_id: r.status for r in data.records}
    found = set(db.scalars(select(Student.id).where(Student.id.in_(wanted))).all())
    missing = sorted(set(wanted) - found)
    if missing:
        raise HTTPException(404, f"دانش‌آموز با شناسه {missing[0]} پیدا نشد.")
    existing = {
        a.student_id: a
        for a in db.scalars(select(Attendance).where(Attendance.day == data.day, Attendance.student_id.in_(wanted)))
    }
    for sid, status in wanted.items():
        if sid in existing:
            existing[sid].status = status
        else:
            db.add(Attendance(student_id=sid, day=data.day, status=status))
    db.commit()
    return {"saved": len(wanted), "day": data.day}


# ---------- Analytics ----------
@app.get("/api/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    return analytics.summary(db)


# Frontend (mounted last so /api routes take priority)
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
