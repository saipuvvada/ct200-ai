from typing import List, Optional
from sqlalchemy import ForeignKey, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Node(Base):
    """
    Represents a node within the document hierarchy (e.g. heading, subheading, table, list, paragraph).
    """
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    logical_node_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    heading: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="nodes")
    parent: Mapped[Optional["Node"]] = relationship(
        "Node",
        back_populates="children",
        remote_side=[id]
    )
    children: Mapped[List["Node"]] = relationship(
        "Node",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="Node.order_index"
    )
    selection_items: Mapped[List["SelectionItem"]] = relationship(
        "SelectionItem",
        back_populates="node",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Node(id={self.id}, logical_node_id='{self.logical_node_id}', "
            f"heading='{self.heading[:30] if self.heading else None}', level={self.level})>"
        )
