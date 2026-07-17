import logging
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.node import Node
from app.models.selection import Selection, SelectionItem
from app.schemas.selection import SelectionCreate, SelectionResponse

logger = logging.getLogger(__name__)

class SelectionService:
    @staticmethod
    def create_selection(db: Session, data: SelectionCreate) -> SelectionResponse:
        # Validate document exists
        doc = db.query(Document).filter(Document.id == data.document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Deduplicate node_ids
        unique_node_ids = list(set(data.node_ids))

        # Validate nodes exist and belong to the document
        nodes = db.query(Node).filter(Node.id.in_(unique_node_ids)).all()
        if len(nodes) != len(unique_node_ids):
            raise HTTPException(status_code=400, detail="One or more nodes do not exist")

        for node in nodes:
            if node.document_id != data.document_id:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Node {node.id} does not belong to document {data.document_id}"
                )

        # Create Selection
        selection = Selection(
            name=data.name,
            document_id=data.document_id
        )
        db.add(selection)
        db.flush() # flush to get selection.id

        # Create Selection Items
        items = []
        for node_id in unique_node_ids:
            item = SelectionItem(selection_id=selection.id, node_id=node_id)
            items.append(item)
            db.add(item)
        
        db.commit()
        db.refresh(selection)
        
        return SelectionResponse.model_validate(selection)

    @staticmethod
    def get_selections(db: Session) -> List[SelectionResponse]:
        selections = db.query(Selection).order_by(Selection.created_at.desc()).all()
        return [SelectionResponse.model_validate(s) for s in selections]

    @staticmethod
    def get_selection(db: Session, selection_id: int) -> Optional[SelectionResponse]:
        selection = db.query(Selection).filter(Selection.id == selection_id).first()
        if not selection:
            return None
        return SelectionResponse.model_validate(selection)

    @staticmethod
    def delete_selection(db: Session, selection_id: int) -> bool:
        selection = db.query(Selection).filter(Selection.id == selection_id).first()
        if not selection:
            return False
            
        db.delete(selection)
        db.commit()
        return True
