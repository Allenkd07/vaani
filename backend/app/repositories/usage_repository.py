from datetime import date

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.models import DailyUsage

_INSERT = {"postgresql": postgresql.insert, "sqlite": sqlite.insert}


class UsageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def try_increment(self, day: date, limit: int) -> bool:
        """Atomically counts one session for `day` unless `limit` is reached; returns whether it was counted.

        A single upsert with a guarded update means concurrent sessions can never push the count past the limit.
        """
        insert = _INSERT[self.db.get_bind().dialect.name]
        statement = (
            insert(DailyUsage)
            .values(day=day, sessions=1)
            .on_conflict_do_update(
                index_elements=[DailyUsage.day],
                set_={"sessions": DailyUsage.sessions + 1},
                where=DailyUsage.sessions < limit,
            )
            .returning(DailyUsage.sessions)
        )
        counted = self.db.execute(statement).first() is not None
        self.db.commit()
        return counted
