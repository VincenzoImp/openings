"""Doubles of time: a clock the test moves by hand and the stop event of a worker lane.

Nothing sleeps: a lane's idle wait advances the clock, if it has one, and stops the
loop after a given number of waits.
"""

from datetime import UTC, datetime, timedelta

START = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)


class Clock:
    """A clock that moves only when the test advances it; calling it gives epoch seconds."""

    def __init__(self, start=START):
        self.start = self.moment = start

    def __call__(self):
        return self.moment.timestamp()

    def advance(self, seconds):
        self.moment += timedelta(seconds=seconds)

    def stamp(self, offset=0):
        return (self.moment + timedelta(seconds=offset)).isoformat(timespec="microseconds")

    @property
    def elapsed(self):
        return (self.moment - self.start).total_seconds()


class Lane:
    """The stop event of a worker loop: set after ``idle`` waits, each advancing ``clock``."""

    def __init__(self, idle=1, clock=None):
        self.clock, self.idle, self.waits, self.stopped = clock, idle, [], False

    def is_set(self):
        return self.stopped

    def wait(self, seconds):
        self.waits.append(seconds)
        if self.clock:
            self.clock.advance(seconds)
        self.stopped = len(self.waits) >= self.idle
        return self.stopped
