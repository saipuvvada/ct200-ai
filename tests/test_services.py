import pytest
from app.utils.hashing import normalize_text, calculate_content_hash
from app.services.document_service import import_document_version
from app.schemas.parser import ParsedNode
from app.models.document import Document
from app.models.node import Node

def test_normalize_text():
    """
    Verify text normalization removes excessive whitespaces, tabs, and carriage returns.
    """
    assert normalize_text("  hello   world  ") == "hello world"
    assert normalize_text("\nhello\t\tworld\r") == "hello world"
    assert normalize_text(None) == ""
    assert normalize_text("") == ""


def test_calculate_content_hash_stability():
    """
    Verify SHA256 hashes are stable and unaffected by trailing or double spaces.
    """
    h1 = calculate_content_hash("1. Introduction", "This is the manual text.")
    h2 = calculate_content_hash(" 1. Introduction ", "\nThis  is \t the manual text. ")
    
    assert h1 == h2
    assert len(h1) == 64  # SHA256 string length

    # Modifying actual character content should change the hash
    h3 = calculate_content_hash("1. Introduction", "This is the manual text edited.")
    assert h1 != h3


def test_import_document_version_relational_hierarchy(db_session):
    """
    Test importing a recursive ParsedNode tree into the database.
    Asserts database tables are properly linked and contain correct fields.
    """
    # 1. Build a dummy ParsedNode hierarchy
    # virtual root
    root = ParsedNode(
        heading="Document Root",
        level=0,
        node_type="heading",
        order_index=0
    )
    # level 1 heading
    h1 = ParsedNode(
        heading="1. First Section",
        level=1,
        node_type="heading",
        order_index=1
    )
    # level 2 subheading
    h1_1 = ParsedNode(
        heading="1.1 Subheading",
        level=2,
        node_type="heading",
        order_index=2
    )
    # paragraph block inside subheading
    para1 = ParsedNode(
        body="This is paragraph text in 1.1.",
        level=3,
        node_type="paragraph",
        order_index=3
    )
    
    # Nest nodes
    h1_1.children.append(para1)
    h1.children.append(h1_1)
    root.children.append(h1)

    # 2. Execute import
    doc = import_document_version(
        db=db_session,
        filename="CT-200.pdf",
        version="v1",
        parsed_root=root
    )

    # 3. Assertions
    # Verify document record
    assert doc.id is not None
    assert doc.filename == "CT-200.pdf"
    assert doc.version == "v1"

    # Query nodes from database
    db_nodes = db_session.query(Node).filter(Node.document_id == doc.id).all()
    assert len(db_nodes) == 3

    # Heading level 1 node check
    db_h1 = db_session.query(Node).filter(Node.heading == "1. First Section").one()
    assert db_h1.level == 1
    assert db_h1.parent_id is None
    assert db_h1.order_index == 1
    assert len(db_h1.logical_node_id) == 32

    # Heading level 2 node check
    db_h1_1 = db_session.query(Node).filter(Node.heading == "1.1 Subheading").one()
    assert db_h1_1.level == 2
    assert db_h1_1.parent_id == db_h1.id
    assert db_h1_1.order_index == 2

    # Paragraph node check
    db_para = db_session.query(Node).filter(Node.heading.is_(None)).one()
    assert db_para.body == "This is paragraph text in 1.1."
    assert db_para.parent_id == db_h1_1.id
    assert db_para.order_index == 3
    
    # Test unique constraint value error on re-import
    with pytest.raises(ValueError):
        import_document_version(
            db=db_session,
            filename="CT-200.pdf",
            version="v1",
            parsed_root=root
        )
