"""Scheduler state models for preventing duplicate job execution."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class SchedulerState(Base):
    """
    Scheduler state table for tracking job execution.

    Used to prevent duplicate execution in multi-worker environments.
    Each worker checks this table before executing a scheduled job.
    """

    __tablename__ = "scheduler_state"

    job_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_run_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
