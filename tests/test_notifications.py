from datetime import datetime

from models import Course, Snapshot, Turma
from notifications import (
    format_course_diff_message,
    format_turma_diff_message,
    format_weekly_report,
)
from state_manager import CourseDiff, TurmaDiff


def _sample_snapshot() -> Snapshot:
    course = Course(
        course_id=1,
        name="Python Fundamentals",
        slug="python-fundamentals",
        modality="Presencial",
        level="Cursos Livres",
        area="TI",
        description="Desc",
        workload_hours=40,
        units=[],
    )
    turma = Turma(
        turma_id="1",
        course_id=1,
        unit_id=10,
        course_name="Python Fundamentals",
        unit_name="Osasco - Centro",
        start_date="15/03/2026",
        end_date="20/04/2026",
        spots_total=30,
        spots_left=20,
        schedule_type="Segunda a Sexta",
        shift="Noite",
    )
    course.units = []
    return Snapshot(at=datetime(2026, 3, 1), courses=[course], turmas=[turma])


def test_format_course_diff_message_contains_sections():
    course_new = Course(
        course_id=1,
        name="New Course",
        slug="new-course",
        modality="Presencial",
        level="Cursos Livres",
        area="TI",
        description="Desc",
        workload_hours=40,
        units=[],
    )
    diff = CourseDiff(new_courses=[course_new], deleted_courses=[], modified_courses=[])
    msg = format_course_diff_message(diff)
    assert "New Courses" in msg
    assert "New Course" in msg


def test_format_turma_diff_message_contains_counts():
    course_name = "Python Fundamentals"
    unit_name = "Osasco - Centro"
    t_new = Turma(
        turma_id="1",
        course_id=1,
        unit_id=10,
        course_name=course_name,
        unit_name=unit_name,
        start_date="15/03/2026",
        end_date="20/04/2026",
        spots_total=30,
        spots_left=20,
        schedule_type="Segunda a Sexta",
        shift="Noite",
    )
    diff = TurmaDiff(new_turmas=[t_new], deleted_turmas=[], spot_changes=[])
    msg = format_turma_diff_message(diff)
    assert "New Classes" in msg
    assert course_name in msg
    assert unit_name in msg


def test_format_weekly_report_has_header():
    snapshot = _sample_snapshot()
    msg = format_weekly_report(snapshot)
    assert "SENAI Courses Weekly Report" in msg
    assert "Python Fundamentals" in msg

