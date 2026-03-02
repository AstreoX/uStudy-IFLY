"""Scheduler module for background scheduled tasks."""

from scheduler.core import get_scheduler_lifespan, scheduler

__all__ = ["scheduler", "get_scheduler_lifespan"]
