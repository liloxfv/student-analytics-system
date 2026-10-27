"""Fill the database with SYNTHETIC demo data (no real students).

    python -m app.seed          # only if the database is empty
    python -m app.seed --reset  # wipe and re-seed
"""
import random
import sys
from datetime import date, timedelta

from sqlalchemy import select

from .database import SessionLocal, engine
from .models import Attendance, Base, Grade, Student, Subject

FIRST = ["علی", "سارا", "محمد", "زهرا", "رضا", "مریم", "امیر", "نگار", "حسین", "الهام", "پارسا", "فاطمه", "کیان", "ترانه", "آرین", "هانیه"]
LAST = ["احمدی", "رضایی", "موسوی", "کریمی", "حسینی", "نوری", "صادقی", "جلالی", "فرهادی", "کاظمی", "یوسفی", "مرادی"]
CLASSES = [("دهم", "۱۰-الف"), ("دهم", "۱۰-ب"), ("یازدهم", "۱۱-الف")]
SUBJECTS = ["ریاضی", "فیزیک", "برنامه‌نویسی", "شبکه", "زبان انگلیسی", "ادبیات"]


def clamp(x, lo=0.0, hi=20.0):
    return max(lo, min(hi, x))


def main():
    rng = random.Random(42)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if "--reset" in sys.argv:
            for model in (Attendance, Grade, Student, Subject):
                for row in db.scalars(select(model)):
                    db.delete(row)
            db.commit()
        elif db.scalar(select(Student.id).limit(1)):
            print("Database already has data. Use --reset to re-seed.")
            return

        subjects = [Subject(name=n) for n in SUBJECTS]
        db.add_all(subjects)
        names = rng.sample([(f, l) for f in FIRST for l in LAST], 24)
        students = []
        for i, (f, l) in enumerate(names):
            level, cls = CLASSES[i % len(CLASSES)]
            students.append(Student(student_code=f"S{1001 + i}", first_name=f, last_name=l, grade_level=level, class_name=cls))
        db.add_all(students)
        db.flush()

        today = date.today()
        exam_days = [today - timedelta(days=7 * k) for k in range(5, -1, -1)]
        for s in students:
            for subj in subjects:
                base = clamp(rng.gauss(14, 3), 6, 19)
                drift = rng.uniform(-0.8, 0.8)
                for i, d in enumerate(exam_days):
                    score = clamp(base + drift * i + rng.gauss(0, 1))
                    db.add(Grade(student_id=s.id, subject_id=subj.id, score=round(score * 4) / 4, exam_date=d, title=f"آزمون {i + 1}"))

        days = [today - timedelta(days=k) for k in range(20) if (today - timedelta(days=k)).weekday() not in (3, 4)][:12]
        for s in students:
            skip = rng.choice([0.03, 0.08, 0.2])
            for d in days:
                r = rng.random()
                status = "absent" if r < skip else "late" if r < skip + 0.06 else "present"
                db.add(Attendance(student_id=s.id, day=d, status=status))
        db.commit()
        print(f"Seeded {len(students)} students, {len(subjects)} subjects.")


if __name__ == "__main__":
    main()
