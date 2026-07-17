import logging
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from app.models.document import Document
from app.models.node import Node
from app.schemas.browse import (
    DocumentResponse, SectionResponse, NodeResponse, 
    SearchResponse, ChangeResponse, DiffSummary
)

logger = logging.getLogger(__name__)

class BrowseService:
    @staticmethod
    def list_documents(db: Session) -> List[DocumentResponse]:
        documents = db.query(Document).order_by(Document.created_at.desc()).all()
        result = []
        for doc in documents:
            total_nodes = db.query(func.count(Node.id)).filter(Node.document_id == doc.id).scalar()
            doc_dict = {
                "id": doc.id,
                "filename": doc.filename,
                "version": doc.version,
                "created_at": doc.created_at,
                "total_nodes": total_nodes or 0
            }
            result.append(DocumentResponse.model_validate(doc_dict))
        return result

    @staticmethod
    def get_sections(db: Session, document_id: int, version: Optional[str] = None) -> List[SectionResponse]:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return None
        
        target_doc = doc
        if version:
            if version.lower() == "latest":
                target_doc = db.query(Document).filter(
                    Document.filename == doc.filename
                ).order_by(Document.created_at.desc()).first()
            else:
                target_doc = db.query(Document).filter(
                    Document.filename == doc.filename,
                    Document.version == version
                ).first()
                
            if not target_doc:
                return None
                
        # Get root nodes (parent_id is NULL)
        root_nodes = db.query(Node).filter(
            Node.document_id == target_doc.id,
            Node.parent_id.is_(None)
        ).order_by(Node.order_index.asc()).all()

        result = []
        for node in root_nodes:
            has_children = db.query(func.count(Node.id)).filter(Node.parent_id == node.id).scalar() > 0
            result.append(SectionResponse(
                id=node.id,
                logical_node_id=node.logical_node_id,
                heading=node.heading,
                level=node.level,
                content_hash=node.content_hash,
                has_children=has_children
            ))
        return result

    @staticmethod
    def get_node_details(db: Session, node_id: int) -> Optional[NodeResponse]:
        def build_tree(node, doc_version):
            node_resp = NodeResponse.model_validate(node)
            node_resp.document_version = doc_version
            node_resp.children = [build_tree(child, doc_version) for child in node.children]
            return node_resp
            
        # Recursive fetch with eager loading of children avoids N+1 queries.
        node = db.query(Node).filter(Node.id == node_id).first()
        if not node:
            return None
            
        doc = db.query(Document).filter(Document.id == node.document_id).first()
        return build_tree(node, doc.version if doc else None)

    @staticmethod
    def search(db: Session, query: str, version: Optional[str] = None, heading_only: bool = False) -> List[SearchResponse]:
        # Subquery to find target documents
        doc_query = db.query(Document)
        if version:
            if version.lower() == "latest":
                # Find latest document per filename
                subq = db.query(Document.filename, func.max(Document.created_at).label('max_date')).group_by(Document.filename).subquery()
                doc_query = doc_query.join(subq, (Document.filename == subq.c.filename) & (Document.created_at == subq.c.max_date))
            else:
                doc_query = doc_query.filter(Document.version == version)
        
        target_doc_ids = [doc.id for doc in doc_query.all()]
        if not target_doc_ids:
            return []

        q = db.query(Node).join(Document).filter(Node.document_id.in_(target_doc_ids))
        
        if heading_only:
            q = q.filter(Node.node_type == "heading")
            q = q.filter(Node.heading.ilike(f"%{query}%"))
        else:
            q = q.filter(or_(
                Node.heading.ilike(f"%{query}%"),
                Node.body.ilike(f"%{query}%")
            ))
            
        nodes = q.order_by(Node.order_index.asc()).all()
        result = []
        for node in nodes:
            snippet_text = node.body if node.body else (node.heading if node.heading else "")
            snippet = snippet_text[:200]
            
            result.append(SearchResponse(
                node_id=node.id,
                heading=node.heading,
                snippet=snippet,
                document_version=node.document.version,
                logical_node_id=node.logical_node_id
            ))
        return result

    @staticmethod
    def get_node_changes(db: Session, node_id: int) -> Optional[ChangeResponse]:
        current_node = db.query(Node).filter(Node.id == node_id).first()
        if not current_node:
            return None
            
        current_doc = db.query(Document).filter(Document.id == current_node.document_id).first()
        
        # Find the previous version of the document
        prev_doc = db.query(Document).filter(
            Document.filename == current_doc.filename,
            Document.created_at < current_doc.created_at
        ).order_by(Document.created_at.desc()).first()
        
        if not prev_doc:
            return ChangeResponse(changed=False)
            
        # Find the matching node in the previous document
        prev_node = db.query(Node).filter(
            Node.document_id == prev_doc.id,
            Node.logical_node_id == current_node.logical_node_id
        ).first()
        
        if not prev_node:
            return ChangeResponse(
                changed=True,
                change_type="added",
                current_version=current_doc.version,
                previous_version=prev_doc.version,
                diff_summary=DiffSummary(
                    heading_changed=True,
                    body_changed=True,
                    hash_changed=True
                )
            )
            
        if prev_node.content_hash == current_node.content_hash:
            return ChangeResponse(changed=False)
            
        return ChangeResponse(
            changed=True,
            change_type="modified",
            current_version=current_doc.version,
            previous_version=prev_doc.version,
            diff_summary=DiffSummary(
                heading_changed=(prev_node.heading != current_node.heading),
                body_changed=(prev_node.body != current_node.body),
                hash_changed=(prev_node.content_hash != current_node.content_hash)
            )
        )
