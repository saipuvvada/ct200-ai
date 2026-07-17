from typing import Optional
from bson.objectid import ObjectId
from sqlalchemy.orm import Session
from fastapi import HTTPException
from packaging.version import parse as parse_version
from app.models.document import Document
from app.models.node import Node
from app.database.mongodb import get_generations_collection
from app.schemas.staleness import (
    GenerationStalenessResponse,
    StalenessStatusEnum,
    NodeStaleness
)

class StalenessService:
    @staticmethod
    def get_generation_staleness(db: Session, generation_id: str) -> GenerationStalenessResponse:
        collection = get_generations_collection()
        try:
            gen_doc = collection.find_one({"_id": ObjectId(generation_id)})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid generation ID format")

        if not gen_doc:
            raise HTTPException(status_code=404, detail="Generation not found")

        original_doc_id = gen_doc.get("document_id")
        original_doc_version = gen_doc.get("document_version")
        logical_node_ids = gen_doc.get("logical_node_ids", [])

        # Fetch original document to get filename
        original_doc = db.query(Document).filter(Document.id == original_doc_id).first()
        if not original_doc:
            raise HTTPException(status_code=404, detail="Original document not found in relational DB")

        # Find the latest document with the same filename
        all_versions = db.query(Document).filter(Document.filename == original_doc.filename).all()
        
        # Sort by version number (assuming semantic versioning or numeric strings)
        # Using packaging.version.parse for robust semantic version sorting
        latest_doc = sorted(all_versions, key=lambda d: parse_version(d.version))[-1]

        # Fetch original nodes to get the original hashes
        original_nodes = db.query(Node).filter(
            Node.document_id == original_doc.id,
            Node.logical_node_id.in_(logical_node_ids)
        ).all()
        original_node_map = {n.logical_node_id: n.content_hash for n in original_nodes}

        # If we are already on the latest version, we are Fresh
        if original_doc.version == latest_doc.version:
            node_details = []
            for ln_id in logical_node_ids:
                old_hash = original_node_map.get(ln_id)
                node_details.append(NodeStaleness(
                    logical_node_id=ln_id,
                    status=StalenessStatusEnum.FRESH,
                    old_hash=old_hash,
                    new_hash=old_hash
                ))
            return GenerationStalenessResponse(
                generation_id=generation_id,
                is_stale=False,
                overall_status=StalenessStatusEnum.FRESH,
                latest_document_version=latest_doc.version,
                original_document_version=original_doc_version,
                node_details=node_details
            )

        # There is a newer version. Fetch nodes from the latest version.
        latest_nodes = db.query(Node).filter(
            Node.document_id == latest_doc.id,
            Node.logical_node_id.in_(logical_node_ids)
        ).all()
        latest_node_map = {n.logical_node_id: n.content_hash for n in latest_nodes}

        node_details = []
        overall_status = StalenessStatusEnum.FRESH

        for ln_id in logical_node_ids:
            old_hash = original_node_map.get(ln_id)
            new_hash = latest_node_map.get(ln_id)

            if new_hash is None:
                # Node was removed in the new version
                node_status = StalenessStatusEnum.REMOVED
                overall_status = StalenessStatusEnum.REMOVED
            elif old_hash != new_hash:
                # Node exists but was modified
                node_status = StalenessStatusEnum.MODIFIED
                if overall_status != StalenessStatusEnum.REMOVED:
                    overall_status = StalenessStatusEnum.MODIFIED
            else:
                # Node exists and is unchanged
                node_status = StalenessStatusEnum.FRESH

            node_details.append(NodeStaleness(
                logical_node_id=ln_id,
                status=node_status,
                old_hash=old_hash,
                new_hash=new_hash
            ))

        is_stale = (overall_status in [StalenessStatusEnum.MODIFIED, StalenessStatusEnum.REMOVED])

        # Optional: We could update MongoDB here to reflect the new status
        if is_stale and gen_doc.get("status") == "fresh":
            collection.update_one(
                {"_id": ObjectId(generation_id)},
                {"$set": {"status": overall_status.value.lower()}}
            )

        return GenerationStalenessResponse(
            generation_id=generation_id,
            is_stale=is_stale,
            overall_status=overall_status,
            latest_document_version=latest_doc.version,
            original_document_version=original_doc_version,
            node_details=node_details
        )
