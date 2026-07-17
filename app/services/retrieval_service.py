from typing import List
from sqlalchemy.orm import Session
from app.database.mongodb import get_generations_collection
from app.schemas.retrieval import RetrievalResponse, GenerationWithStaleness
from app.services.staleness_service import StalenessService

class RetrievalService:
    @staticmethod
    def _fetch_and_enrich(db: Session, query: dict, include_staleness: bool) -> RetrievalResponse:
        collection = get_generations_collection()
        cursor = collection.find(query).sort("created_at", -1)
        
        results = []
        for doc in cursor:
            # Prepare the base response
            doc["_id"] = str(doc["_id"])
            generation = GenerationWithStaleness(**doc)
            
            # Enrich with staleness if requested
            if include_staleness:
                staleness_data = StalenessService.get_generation_staleness(db, generation.id)
                generation.staleness = staleness_data
                
            results.append(generation)
            
        return RetrievalResponse(data=results)

    @staticmethod
    def get_generations_by_selection(db: Session, selection_id: int, include_staleness: bool) -> RetrievalResponse:
        query = {"selection_id": selection_id}
        return RetrievalService._fetch_and_enrich(db, query, include_staleness)

    @staticmethod
    def get_generations_by_node(db: Session, logical_node_id: str, include_staleness: bool) -> RetrievalResponse:
        query = {"logical_node_ids": logical_node_id}
        return RetrievalService._fetch_and_enrich(db, query, include_staleness)
