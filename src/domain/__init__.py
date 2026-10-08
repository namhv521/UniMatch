"""Public matching-domain contract."""

from .constraints import validate_assignments
from .models import Advisor, Assignment, Quota, Student, Thesis

__all__ = [
    "Advisor",
    "Assignment",
    "Quota",
    "Student",
    "Thesis",
    "validate_assignments",
]
