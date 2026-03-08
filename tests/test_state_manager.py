import pytest

from models import Course, Snapshot, Turma
from state_manager import CourseDiff, TurmaDiff, diff_courses, diff_turmas


def test_diff_courses_new_and_deleted_and_modified():
    old = [
        Course(
            course_id=1,
            name="Old Course",
            slug="old-course",
            modality="Presencial",
            level="Cursos Livres",
            area="TI",
            description="desc",
            workload_hours=40,
            units=[],
        ),
        Course(
            course_id=2,
            name="Keep Course",
            slug="keep-course",
            modality="Presencial",
            level="Cursos Livres",
            area="TI",
            description="desc",
            workload_hours=40,
            units=[],
        ),
    ]
    new = [
        Course(
            course_id=2,
            name="Keep Course (updated)",
            slug="keep-course",
            modality="Presencial",
            level="Cursos Livres",
            area="TI",
            description="desc",
            workload_hours=60,
            units=[],
        ),
        Course(
            course_id=3,
            name="New Course",
            slug="new-course",
            modality="Presencial",
            level="Cursos Livres",
            area="TI",
            description="desc",
            workload_hours=30,
            units=[],
        ),
    ]

    diff = diff_courses(old, new)
    assert isinstance(diff, CourseDiff)
    assert {c.course_id for c in diff.new_courses} == {3}
    assert {c.course_id for c in diff.deleted_courses} == {1}
    assert {c.course_id for c in diff.modified_courses} == {2}


def test_diff_turmas_new_deleted_and_spot_changes():
    t1_old = Turma(
        turma_id="1",
        course_id=1,
        unit_id=10,
        course_name="Course",
        unit_name="Unit",
        start_date="01/01/2026",
        end_date="01/02/2026",
        spots_total=30,
        spots_left=10,
        schedule_type="Segunda a Sexta",
        shift="Noite",
    )
    t2_old = Turma(
        turma_id="2",
        course_id=1,
        unit_id=10,
        course_name="Course",
        unit_name="Unit",
        start_date="01/03/2026",
        end_date="01/04/2026",
        spots_total=30,
        spots_left=0,
        schedule_type="Sábados",
        shift="Manhã",
    )
    t2_new = Turma(
        turma_id="2",
        course_id=1,
        unit_id=10,
        course_name="Course",
        unit_name="Unit",
        start_date="01/03/2026",
        end_date="01/04/2026",
        spots_total=30,
        spots_left=5,
        schedule_type="Sábados",
        shift="Manhã",
    )
    t3_new = Turma(
        turma_id="3",
        course_id=1,
        unit_id=10,
        course_name="Course",
        unit_name="Unit",
        start_date="01/05/2026",
        end_date="01/06/2026",
        spots_total=30,
        spots_left=20,
        schedule_type="Segunda a Sexta",
        shift="Noite",
    )

    old = [t1_old, t2_old]
    new = [t2_new, t3_new]

    diff = diff_turmas(old, new)
    assert isinstance(diff, TurmaDiff)
    assert {t.turma_id for t in diff.new_turmas} == {"3"}
    assert {t.turma_id for t in diff.deleted_turmas} == {"1"}
    assert len(diff.spot_changes) == 1
    old_t, new_t = diff.spot_changes[0]
    assert old_t.turma_id == "2"
    assert new_t.turma_id == "2"
    assert old_t.spots_left == 0
    assert new_t.spots_left == 5

