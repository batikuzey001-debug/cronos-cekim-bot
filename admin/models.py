from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from database.db import Base


class Bonuses(Base):
    __tablename__ = "bonuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bonus_adi: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    cevrim_kati: Mapped[int] = mapped_column(Integer, nullable=False)
    max_kazanc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WithdrawalLogs(Base):
    __tablename__ = "withdrawal_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cekim_id: Mapped[str] = mapped_column(String(255), nullable=False)
    oyuncu_adi: Mapped[str] = mapped_column(String(255), nullable=False)
    tutar: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=2), nullable=False)
    karar: Mapped[str] = mapped_column(String(20), nullable=False)  # "APPROVED" veya "REJECTED"
    sebep: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Settings(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(String(1024), nullable=False)
