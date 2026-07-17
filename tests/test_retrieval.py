import pytest
from unittest.mock import patch, MagicMock
from bson.objectid import ObjectId
from fastapi.testclient import TestClient
from app.main import app
from datetime import datetime
from app.schemas.staleness import GenerationStalenessResponse, StalenessStatusEnum

@pytest.fixture
def test_client():
    client = TestClient(app)
    yield client

@patch("app.services.retrieval_service.get_generations_collection")
def test_get_generations_by_selection_no_staleness(mock_get_collection, test_client):
    mock_collection = MagicMock()
    
    gen_doc = {
        "_id": ObjectId(),
        "selection_id": 1,
        "document_version": "1",
        "prompt_version": "v1.0",
        "created_at": datetime.now(),
        "status": "fresh",
        "items": [{"question": "Q?", "answer": "A"}]
    }
    
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = [gen_doc]
    mock_collection.find.return_value = mock_cursor
    mock_get_collection.return_value = mock_collection

    response = test_client.get("/api/v1/selections/1/generations")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["selection_id"] == 1
    assert data["data"][0]["staleness"] is None
    
    mock_collection.find.assert_called_with({"selection_id": 1})

@patch("app.services.retrieval_service.get_generations_collection")
@patch("app.services.staleness_service.StalenessService.get_generation_staleness")
def test_get_generations_by_node_with_staleness(mock_get_staleness, mock_get_collection, test_client):
    mock_collection = MagicMock()
    
    gen_id = ObjectId()
    gen_doc = {
        "_id": gen_id,
        "selection_id": 2,
        "document_version": "1",
        "prompt_version": "v1.0",
        "created_at": datetime.now(),
        "status": "fresh",
        "logical_node_ids": ["l1"],
        "items": [{"question": "Q?", "answer": "A"}]
    }
    
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = [gen_doc]
    mock_collection.find.return_value = mock_cursor
    mock_get_collection.return_value = mock_collection

    mock_staleness_response = GenerationStalenessResponse(
        generation_id=str(gen_id),
        is_stale=False,
        overall_status=StalenessStatusEnum.FRESH,
        latest_document_version="1",
        original_document_version="1",
        node_details=[]
    )
    mock_get_staleness.return_value = mock_staleness_response

    response = test_client.get("/api/v1/nodes/l1/generations?include_staleness=true")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    
    assert data["data"][0]["staleness"] is not None
    assert data["data"][0]["staleness"]["is_stale"] is False
    assert data["data"][0]["staleness"]["overall_status"] == "Fresh"

    mock_collection.find.assert_called_with({"logical_node_ids": "l1"})
    from unittest.mock import ANY
    mock_get_staleness.assert_called_with(ANY, str(gen_id))
