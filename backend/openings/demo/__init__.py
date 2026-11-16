"""The demo workspace: one fictional person's job search, for a try-out and the screenshots.

``seed_demo(app)`` fills a new, empty workspace through the services and marks
the file as a demo (``is_demo``). The CVs and letters it stores are package data
beside this module.
"""

from .marker import NotADemo, is_demo, mark_demo, stamp
from .seed import seed_demo

__all__ = ["NotADemo", "is_demo", "mark_demo", "seed_demo", "stamp"]
