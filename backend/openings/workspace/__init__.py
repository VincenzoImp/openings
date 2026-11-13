"""Core archive operations, shared by the dashboard, REST and MCP.

``Workspace`` (service.py) holds settings and the change log and is composed
of the job services (jobs.py, job_changes.py, identity.py, notes.py), the
application services (applications.py, application_changes.py), the timeline
of a job or application (timeline.py), bulk.py and overview.py.
"""

from .service import Workspace

__all__ = ["Workspace"]
