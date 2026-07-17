import datetime
from typing import List
from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Selection(Base):
    """
    Represents a user selection of nodes pinned to a specific document version.
    """
    __tablename__ = "selections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="selections")
    items: Mapped[List["SelectionItem"]] = relationship(
        "SelectionItem",
        back_populates="selection",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Selection(id={self.id}, name='{self.name}', document_id={self.document_id})>"


class SelectionItem(Base):
    """
    Intersection model linking a Selection to a specific Document Node.
    """
    __tablename__ = "selection_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("selections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    selection: Mapped["Selection"] = relationship("Selection", back_populates="items")
    node: Mapped["Node"] = relationship("Node", back_populates="selection_items")

    def __repr__(self) -> str:
        return f"<SelectionItem(id={self.id}, selection_id={self.selection_id}, node_id={self.node_id})>"
