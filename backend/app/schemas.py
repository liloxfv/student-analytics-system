from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StudentIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    student_code: str = Field(min_length=1, max_length=20)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    grade_level: str = Field(min_length=1, max_length=20)
    class_name: str = Field(min_length=1, max_length=30)


class StudentOut(StudentIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    average: float | None = None


class SubjectIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=60)


class SubjectOut(SubjectIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


class GradeIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    student_id: int
    subject_id: int
    score: float = Field(ge=0, le=20, description="Score out of 20")
    exam_date: date
    title: str = Field(default="", max_length=100)


class GradeOut(BaseModel):
    id: int
    student_id: int
    student_name: str
    subject_id: int
    subject_name: str
    score: float
    exam_date: date
    title: str


class AttendanceRecord(BaseModel):
    student_id: int
    status: Literal["present", "absent", "late"]


class AttendanceBulk(BaseModel):
    day: date
    records: list[AttendanceRecord] = Field(min_length=1)


class AttendanceOut(BaseModel):
    student_id: int
    student_name: str
    class_name: str
    day: date
    status: str
