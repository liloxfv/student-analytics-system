"""Read-only statistics. Nothing here invents data: with no records, averages are None."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Attendance, Grade, Student, Subject

MIN_GRADES_FOR_TREND = 3
TREND_THRESHOLD = 0.4  # score points per exam
PASS_MARK = 10


def _r(x, n=2):
    return None if x is None else round(float(x), n)


def attendance_stats(db: Session, student_id: int | None = None) -> dict:
    q = select(Attendance.status, func.count()).group_by(Attendance.status)
    if student_id is not None:
        q = q.where(Attendance.student_id == student_id)
    counts = {"present": 0, "late": 0, "absent": 0}
    counts.update({s: c for s, c in db.execute(q).all()})
    total = sum(counts.values())
    # "late" still counts as attending the session.
    rate = round((counts["present"] + counts["late"]) / total * 100, 1) if total else None
    return {**counts, "total": total, "rate": rate}


def _student_averages(db: Session):
    return db.execute(
        select(Student.id, Student.first_name, Student.last_name, Student.class_name, func.avg(Grade.score))
        .join(Grade, Grade.student_id == Student.id)
        .group_by(Student.id)
    ).all()


def summary(db: Session) -> dict:
    averages = _student_averages(db)

    buckets = [("زیر ۱۰", 0, 10), ("۱۰ تا ۱۴", 10, 14), ("۱۴ تا ۱۷", 14, 17), ("۱۷ تا ۲۰", 17, 20.01)]
    distribution = [
        {"label": label, "count": sum(1 for r in averages if lo <= r[4] < hi)} for label, lo, hi in buckets
    ]
    attention = sorted(
        (
            {"id": r[0], "name": f"{r[1]} {r[2]}", "class_name": r[3], "average": _r(r[4])}
            for r in averages
            if r[4] < 12
        ),
        key=lambda x: x["average"],
    )[:5]

    subject_rows = db.execute(
        select(Subject.name, func.avg(Grade.score), func.count(Grade.id))
        .join(Grade, Grade.subject_id == Subject.id)
        .group_by(Subject.id)
    ).all()
    class_rows = db.execute(
        select(Student.class_name, func.avg(Grade.score), func.count(func.distinct(Student.id)))
        .join(Grade, Grade.student_id == Student.id)
        .group_by(Student.class_name)
    ).all()
    timeline = db.execute(
        select(Grade.exam_date, func.avg(Grade.score)).group_by(Grade.exam_date).order_by(Grade.exam_date)
    ).all()

    return {
        "students": db.scalar(select(func.count(Student.id))),
        "subjects": db.scalar(select(func.count(Subject.id))),
        "grades": db.scalar(select(func.count(Grade.id))),
        "average": _r(db.scalar(select(func.avg(Grade.score)))),
        "attendance": attendance_stats(db),
        "subject_averages": sorted(
            ({"name": n, "average": _r(a), "count": c} for n, a, c in subject_rows),
            key=lambda x: x["average"],
            reverse=True,
        ),
        "class_averages": [{"class_name": n, "average": _r(a), "students": c} for n, a, c in class_rows],
        "distribution": distribution,
        "timeline": [{"date": d.isoformat(), "average": _r(a)} for d, a in timeline],
        "attention": attention,
    }


def _slope(values: list[float]) -> float:
    """Least-squares slope of score against exam order (points per exam)."""
    n = len(values)
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    num = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den


def student_report(db: Session, student: Student) -> dict:
    grades = db.execute(
        select(Grade, Subject.name).join(Subject).where(Grade.student_id == student.id).order_by(Grade.exam_date, Grade.id)
    ).all()

    by_subject: dict[int, dict] = {}
    for g, name in grades:
        s = by_subject.setdefault(g.subject_id, {"subject_id": g.subject_id, "name": name, "points": []})
        s["points"].append({"date": g.exam_date.isoformat(), "score": g.score})

    subjects, insights = [], []
    for s in by_subject.values():
        scores = [p["score"] for p in s["points"]]
        direction = "insufficient"
        if len(scores) >= MIN_GRADES_FOR_TREND:
            slope = _slope(scores)
            direction = "up" if slope >= TREND_THRESHOLD else "down" if slope <= -TREND_THRESHOLD else "flat"
            if direction == "up":
                insights.append(f"در «{s['name']}» روند نمرات رو به بهبود است (حدود {abs(slope):.1f} نمره در هر آزمون).")
            elif direction == "down":
                insights.append(f"در «{s['name']}» روند نمرات کاهشی است (حدود {abs(slope):.1f} نمره در هر آزمون)؛ بهتر است بررسی شود.")
        s.update(average=_r(sum(scores) / len(scores)), count=len(scores), direction=direction)
        subjects.append(s)

    enough = [s for s in subjects if s["count"] >= MIN_GRADES_FOR_TREND]
    for s in enough:
        if s["average"] < PASS_MARK:
            insights.append(f"میانگین «{s['name']}» زیر {PASS_MARK} است و این درس به تمرین بیشتر نیاز دارد.")
    if len(enough) >= 2:
        best = max(enough, key=lambda s: s["average"])
        worst = min(enough, key=lambda s: s["average"])
        if best["average"] - worst["average"] >= 4:
            insights.append(
                f"عملکرد در «{best['name']}» ({best['average']:g}) به‌طور محسوسی بالاتر از «{worst['name']}» ({worst['average']:g}) است."
            )
    if grades and not enough:
        insights.append(f"برای تحلیل روند، حداقل {MIN_GRADES_FOR_TREND} نمره در هر درس لازم است.")

    att = attendance_stats(db, student.id)
    if att["rate"] is not None and att["rate"] < 85:
        insights.append(f"درصد حضور ({att['rate']:g}٪) پایین است.")

    all_scores = [g.score for g, _ in grades]
    by_date: dict[str, list[float]] = {}
    for g, _ in grades:
        by_date.setdefault(g.exam_date.isoformat(), []).append(g.score)

    return {
        "student": {
            "id": student.id,
            "student_code": student.student_code,
            "name": student.full_name,
            "grade_level": student.grade_level,
            "class_name": student.class_name,
        },
        "average": _r(sum(all_scores) / len(all_scores)) if all_scores else None,
        "subjects": sorted(subjects, key=lambda s: s["name"]),
        "timeline": [{"date": d, "average": _r(sum(v) / len(v))} for d, v in sorted(by_date.items())],
        "attendance": att,
        "insights": insights,
    }
