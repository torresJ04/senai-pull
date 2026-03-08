"""Data models for SENAI courses and turmas (classes)."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Unit:
    """SENAI unit (school location)."""
    unit_id: int
    city: str
    neighborhood: str
    phone: str
    address: str
    # Flags used when calling the turmas API (from openModalTurmas)
    estrategia: str = ""
    bolsa: int | None = None
    gratuito: int | None = None
    turno: int | None = None


@dataclass
class Course:
    """A SENAI course (e.g. IT free course)."""
    course_id: int
    name: str
    slug: str
    modality: str  # Presencial, A Distância
    level: str     # Cursos Livres, etc.
    area: str      # Tecnologia da Informação e Informática
    description: str
    workload_hours: Optional[int]
    units: list[Unit] = field(default_factory=list)
    url: str = ""

    def __post_init__(self):
        if not self.url and self.slug:
            self.url = f"https://www.sp.senai.br/curso/{self.slug}/{self.course_id}"


@dataclass
class Turma:
    """A class/turma (schedule with spots and dates)."""
    turma_id: Optional[str]
    course_id: int
    unit_id: int
    course_name: str
    unit_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    spots_total: Optional[int] = None
    spots_left: Optional[int] = None
    schedule_type: Optional[str] = None  # "Segunda a Sexta" or "Sábados"
    shift: Optional[str] = None  # Manhã, Tarde, Noite, Integral
    raw_text: Optional[str] = None

    @property
    def key(self) -> str:
        """Unique key for this turma (for diffing)."""
        return f"{self.course_id}_{self.unit_id}_{self.turma_id or self.raw_text or ''}"


@dataclass
class Snapshot:
    """Full snapshot of courses (and optionally turmas) at a point in time."""
    at: datetime
    courses: list[Course]
    turmas: list[Turma] = field(default_factory=list)
