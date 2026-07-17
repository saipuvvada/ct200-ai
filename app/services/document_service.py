import logging
import uuid
from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.node import Node
from app.schemas.parser import ParsedNode
from app.utils.hashing import calculate_content_hash

logger = logging.getLogger(__name__)

def import_document_version(
    db: Session,
    filename: str,
    version: str,
    parsed_root: ParsedNode,
    logical_node_map: Optional[Dict[int, str]] = None
) -> Document:
    """
    Saves a parsed document version and its entire node hierarchy into the SQLite database.
    
    :param db: SQLAlchemy Session.
    :param filename: Filename of the document.
    :param version: Version tag of the document.
    :param parsed_root: Root ParsedNode from the extractor.
    :param logical_node_map: Optional dictionary mapping parsed node order_indexes to
                             existing logical_node_ids (used for version alignment in Phase 6).
    :return: The created Document object.
    """
    # Check if this document version combination already exists
    existing = db.query(Document).filter(
        Document.filename == filename,
        Document.version == version
    ).first()
    if existing:
        raise ValueError(f"Document version already exists: '{filename}' version '{version}'")

    logger.info(f"Importing document '{filename}' version '{version}' into SQLite")

    # Create document record
    doc = Document(filename=filename, version=version)
    db.add(doc)
    db.flush()  # Get generated document.id

    def save_node(parsed_node: ParsedNode, parent_id: Optional[int] = None) -> None:
        """
        Recursively saves ParsedNode tree nodes to SQLite.
        """
        # Calculate content hash for the node (Phase 5)
        content_hash = calculate_content_hash(parsed_node.heading, parsed_node.body)

        # Resolve logical_node_id
        # If logical_node_map contains a pre-matched logical_node_id, use it; otherwise generate fresh UUID.
        logical_node_id = None
        if logical_node_map and parsed_node.order_index in logical_node_map:
            logical_node_id = logical_node_map[parsed_node.order_index]
        else:
            logical_node_id = uuid.uuid4().hex

        # Create database Node
        db_node = Node(
            logical_node_id=logical_node_id,
            document_id=doc.id,
            parent_id=parent_id,
            heading=parsed_node.heading,
            level=parsed_node.level,
            body=parsed_node.body,
            order_index=parsed_node.order_index,
            content_hash=content_hash
        )
        db.add(db_node)
        db.flush()  # Retrieve db_node.id for child mapping

        # Recurse on children
        for child in parsed_node.children:
            save_node(child, db_node.id)

    # parsed_root is the virtual "Document Root". We only save actual document children.
    for child in parsed_root.children:
        save_node(child, parent_id=None)

    db.commit()
    logger.info(f"Successfully imported document version '{version}' with ID {doc.id}")
    return doc
