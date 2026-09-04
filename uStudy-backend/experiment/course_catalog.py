"""Stable identifiers and policy helpers for experiment-managed courses."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ManagedCourse:
    """A course whose lifecycle is controlled by the experiment deployment."""

    id: UUID
    name: str


DATA_STRUCTURES_SPACE_ID = UUID("fb40acea-11d5-572f-b987-e08cf9e152b5")
COMPUTER_NETWORKS_SPACE_ID = UUID("d0fcc14b-56a5-4fa9-9f30-07cb712d8e5d")
OPERATING_SYSTEMS_SPACE_ID = UUID("f69c53cf-e561-4e12-884c-88e3a35659dc")

MANAGED_COURSES = (
    ManagedCourse(DATA_STRUCTURES_SPACE_ID, "数据结构"),
    ManagedCourse(COMPUTER_NETWORKS_SPACE_ID, "计算机网络"),
    ManagedCourse(OPERATING_SYSTEMS_SPACE_ID, "计算机操作系统"),
)
MANAGED_COURSE_BY_ID = {course.id: course for course in MANAGED_COURSES}
MANAGED_COURSE_IDS = frozenset(MANAGED_COURSE_BY_ID)


def is_managed_course(space_id: UUID) -> bool:
    """Return whether the space has an experiment-managed lifecycle."""

    return space_id in MANAGED_COURSE_IDS
