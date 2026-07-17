import pytest
from sqlalchemy.exc import IntegrityError
from app.models.document import Document
from app.models.node import Node
from app.models.selection import Selection, SelectionItem

def test_document_unique_constraint(db_session):
    """
    Verify that UniqueConstraint(filename, version) is enforced.
    """
    doc1 = Document(filename="CT-200.pdf", version="v1")
    db_session.add(doc1)
    db_session.commit()

    # Try inserting the same combination
    doc2 = Document(filename="CT-200.pdf", version="v1")
    db_session.add(doc2)
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_node_parent_child_hierarchy(db_session):
    """
    Verify that nested Node structure respects parent-child self-references
    and orders children correctly by order_index.
    """
    doc = Document(filename="CT-200.pdf", version="v1")
    db_session.add(doc)
    db_session.commit()

    # Create root heading node
    parent_node = Node(
        logical_node_id="logical-1",
        document_id=doc.id,
        heading="1. Overview",
        level=1,
        body="This is section 1",
        order_index=1,
        content_hash="hash-1"
    )
    db_session.add(parent_node)
    db_session.commit()

    # Create sub-nodes out of order_index order to test sorting
    child_node_2 = Node(
        logical_node_id="logical-3",
        document_id=doc.id,
        parent_id=parent_node.id,
        heading="1.2 Scope",
        level=2,
        body="This is scope",
        order_index=3,
        content_hash="hash-3"
    )
    child_node_1 = Node(
        logical_node_id="logical-2",
        document_id=doc.id,
        parent_id=parent_node.id,
        heading="1.1 Intro",
        level=2,
        body="This is intro",
        order_index=2,
        content_hash="hash-2"
    )
    db_session.add_all([child_node_2, child_node_1])
    db_session.commit()

    # Refresh parent node from DB
    db_session.refresh(parent_node)
    assert len(parent_node.children) == 2
    # Verify order_index sorts children correctly
    assert parent_node.children[0].id == child_node_1.id
    assert parent_node.children[1].id == child_node_2.id

def test_cascade_delete(db_session):
    """
    Verify that deleting a document cascade deletes all its nodes and selections.
    """
    doc = Document(filename="CT-200.pdf", version="v1")
    db_session.add(doc)
    db_session.commit()

    node = Node(
        logical_node_id="logical-1",
        document_id=doc.id,
        heading="1. Section",
        level=1,
        body="Body content",
        order_index=1,
        content_hash="hash-1"
    )
    selection = Selection(
        name="My Selection",
        document_id=doc.id
    )
    db_session.add_all([node, selection])
    db_session.commit()

    item = SelectionItem(
        selection_id=selection.id,
        node_id=node.id
    )
    db_session.add(item)
    db_session.commit()

    # Check existence
    assert db_session.query(Node).count() == 1
    assert db_session.query(Selection).count() == 1
    assert db_session.query(SelectionItem).count() == 1

    # Delete document
    db_session.delete(doc)
    db_session.commit()

    # Verify everything cascade deleted
    assert db_session.query(Node).count() == 0
    assert db_session.query(Selection).count() == 0
    assert db_session.query(SelectionItem).count() == 0
