import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.selection import Selection
from app.database.mongodb import get_generations_collection
from app.llm.generator import generate_qa, PROMPT_VERSION
from app.schemas.generation import GenerationResponse

class GenerationService:
    @staticmethod
    def generate_for_selection(db: Session, selection_id: int) -> GenerationResponse:
        # 1. Fetch selection and its nodes
        selection = db.query(Selection).filter(Selection.id == selection_id).first()
        if not selection:
            raise HTTPException(status_code=404, detail="Selection not found")

        if not selection.items:
            raise HTTPException(status_code=400, detail="Selection has no nodes to generate from")

        # 2. Extract content from all selected nodes
        # Sort items by node order to maintain context flow
        sorted_nodes = sorted([item.node for item in selection.items], key=lambda n: n.order_index)
        
        text_chunks = []
        for node in sorted_nodes:
            if node.heading:
                text_chunks.append(f"Heading: {node.heading}")
            if node.body:
                text_chunks.append(node.body)
                
        full_text = "\n\n".join(text_chunks)
        
        if not full_text.strip():
            raise HTTPException(status_code=400, detail="Nodes in selection contain no extractable text")

        # 3. Call LLM (throws RuntimeError if validation/retries fail)
        generation_result = generate_qa(full_text)

        # 4. Save to MongoDB
        doc = {
            "selection_id": selection.id,
            "document_id": selection.document_id,
            "document_version": selection.document.version,
            "logical_node_ids": [node.logical_node_id for node in sorted_nodes],
            "prompt_version": PROMPT_VERSION,
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "status": "fresh",
            "items": [item.model_dump() for item in generation_result.items]
        }
        
        collection = get_generations_collection()
        insert_result = collection.insert_one(doc)
        
        # 5. Return response
        doc["_id"] = str(insert_result.inserted_id)
        return GenerationResponse(**doc)
