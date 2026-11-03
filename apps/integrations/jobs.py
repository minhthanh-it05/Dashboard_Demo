"""Registry of sync jobs that can be started from the UI.

Domain apps register their jobs in AppConfig.ready(), so this app never
imports domain code.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SyncJob:
    key: str
    label: str
    system: str
    run: Callable  # run(user=None) -> list[SyncRun]


_jobs = {}


def register(job):
    _jobs[job.key] = job


def get_job(key):
    return _jobs.get(key)


def all_jobs():
    return list(_jobs.values())
