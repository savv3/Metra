"""Which snapshots to keep.

Every automatic snapshot (nightly, before an upgrade, before a risky action)
is kept for ``days`` days. Older ones thin out: the newest of each week is
kept for ``weeks`` weeks and the newest of each month for ``months`` months.
Snapshots someone took by hand are kept until someone deletes them.
"""

import datetime
from dataclasses import dataclass

from .archive import parse_name

# Snapshots taken by hand, from the Backups page or the command line.
KEPT_UNTIL_DELETED = {"manual"}


@dataclass(frozen=True)
class Policy:
    days: int = 7
    weeks: int = 4
    months: int = 12

    @classmethod
    def from_settings(cls, config):
        return cls(config["keep_days"], config["keep_weeks"], config["keep_months"])

    def to_delete(self, names, now):
        """The names of the snapshots to delete, oldest first. ``now`` is
        local time without a time zone, like the times in the names."""
        infos = sorted(
            (info for info in map(parse_name, names) if info),
            key=lambda info: info.taken,
            reverse=True,  # newest first, so the first of a week or month is its newest
        )
        keep, weeks_seen, months_seen = set(), set(), set()
        for info in infos:
            age = now - info.taken
            week = info.taken.isocalendar()[:2]
            month = (info.taken.year, info.taken.month)
            if info.trigger in KEPT_UNTIL_DELETED:
                # Kept anyway, so it does not take the place of its week's or month's.
                keep.add(info.name)
                continue
            if age <= datetime.timedelta(days=self.days):
                keep.add(info.name)
            if age <= datetime.timedelta(weeks=self.weeks) and week not in weeks_seen:
                weeks_seen.add(week)
                keep.add(info.name)
            if months_between(info.taken, now) < self.months and month not in months_seen:
                months_seen.add(month)
                keep.add(info.name)
        return [info.name for info in reversed(infos) if info.name not in keep]


def months_between(earlier, later):
    return (later.year - earlier.year) * 12 + later.month - earlier.month
