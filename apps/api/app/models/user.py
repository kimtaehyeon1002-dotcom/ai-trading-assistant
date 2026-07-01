"""사용자 + 인증수단. (설계서 §4.2)"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "user"

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    # OWNER | MEMBER | ADMIN  (10~100명 확장 대비)
    role: Mapped[str] = mapped_column(String(16), default="OWNER", nullable=False)
    # {scalping, swing, long}
    investment_styles: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )
    locale: Mapped[str] = mapped_column(String(8), default="ko", nullable=False)
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Seoul", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    # 요금제(Phase 7): free | pro | enterprise — 일일 비용 쿼터/모델 티어 결정
    plan: Mapped[str] = mapped_column(String(16), default="free", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    credentials: Mapped[list["AuthCredential"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthCredential(Base):
    """로컬/OAuth/외부 브로커(KIS) 인증수단. 시크릿은 봉투암호화하여 secret_enc에 저장."""

    __tablename__ = "auth_credential"
    __table_args__ = (UniqueConstraint("provider", "provider_subject"),)

    credential_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.user_id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # local|google|kis|apikey
    provider_subject: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    secret_enc: Mapped[bytes | None] = mapped_column(LargeBinary)  # KMS/Vault 봉투암호화
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="credentials")
