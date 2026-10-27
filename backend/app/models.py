from datetime import date

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MAX_SCORE = 20


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_code: Mapped[str] = mapped_column(String(20), unique=True)
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    grade_level: Mapped[str] = mapped_column(String(20))
    class_name: Mapped[str] = mapped_column(String(30), index=True)

    grades: Mapped[list["Grade"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    attendance: Mapped[list["Attendance"]] = relationship(back_populates="student", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)

    grades: Mapped[list["Grade"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (CheckConstraint(f"score >= 0 AND score <= {MAX_SCORE}", name="ck_grade_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float)
    exam_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(100), default="")

    student: Mapped[Student] = relationship(back_populates="grades")
    subject: Mapped[Subject] = relationship(back_populates="grades")


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "day", name="uq_attendance_student_day"),
        CheckConstraint("status IN ('present','absent','late')", name="ck_attendance_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(10))

    student: Mapped[Student] = relationship(back_populates="attendance")
