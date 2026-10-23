from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DailyUsage(Base):
    """Live sessions started per quota day (Pacific time, matching the Gemini API's daily reset)."""

    __tablename__ = "stt_daily_usage"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    sessions: Mapped[int] = mapped_column(Integer, nullable=False)
