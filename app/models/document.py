import datetime
from typing import List
from sqlalchemy import String, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Document(Base):
    """
    Represents a parsed document version (e.g. CT-200 v1, CT-200 v2).
    """
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("filename", "version", name="uq_document_filename_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    nodes: Mapped[List["Node"]] = relationship(
        "Node",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    selections: Mapped[List["Selection"]] = relationship(
        "Selection",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename='{self.filename}', version='{self.version}')>"
