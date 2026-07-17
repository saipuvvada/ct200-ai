import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.document import Document
from app.models.node import Node
from app.models.selection import Selection, SelectionItem
from sqlalchemy.orm import Session
from app.database.session import get_db

@pytest.fixture
def test_client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture
def setup_generation_data(db_session: Session):
    doc1 = Document(filename="CT-200", version="1")
    db_session.add(doc1)
    db_session.commit()

    n1 = Node(logical_node_id="l1", document_id=doc1.id, heading="Battery", level=1, order_index=1, content_hash="h1", node_type="heading")
    n2 = Node(logical_node_id="l2", document_id=doc1.id, body="The battery is 12V.", level=1, order_index=2, content_hash="h2", node_type="paragraph")
    
    db_session.add(n1)
    db_session.add(n2)
    db_session.commit()

    selection = Selection(name="Battery Selection", document_id=doc1.id)
    db_session.add(selection)
    db_session.commit()

    item1 = SelectionItem(selection_id=selection.id, node_id=n1.id)
    item2 = SelectionItem(selection_id=selection.id, node_id=n2.id)
    db_session.add(item1)
    db_session.add(item2)
    db_session.commit()

    return {"doc1": doc1.id, "selection1": selection.id}

@patch("app.services.generation_service.get_generations_collection")
@patch("app.llm.generator.httpx.post")
def test_generate_qa_success(mock_post, mock_get_collection, test_client, setup_generation_data):
    # Mock LLM API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"items": [{"question": "What is the voltage?", "answer": "12V"}]}'
                }
            }
        ]
    }
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # Mock MongoDB
    mock_collection = MagicMock()
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = "mongodb_id_123"
    mock_collection.insert_one.return_value = mock_insert_result
    mock_get_collection.return_value = mock_collection

    response = test_client.post(f"/api/v1/selections/{setup_generation_data['selection1']}/generate")
    
    assert response.status_code == 200
    data = response.json()
    assert data["_id"] == "mongodb_id_123"
    assert data["selection_id"] == setup_generation_data["selection1"]
    assert data["document_version"] == "1"
    assert data["status"] == "fresh"
    assert len(data["items"]) == 1
    assert data["items"][0]["question"] == "What is the voltage?"

    # Ensure DB insert was called
    mock_collection.insert_one.assert_called_once()
    inserted_doc = mock_collection.insert_one.call_args[0][0]
    assert inserted_doc["logical_node_ids"] == ["l1", "l2"]

@patch("app.services.generation_service.get_generations_collection")
@patch("app.llm.generator.httpx.post")
def test_generate_qa_retry_on_malformed_json(mock_post, mock_get_collection, test_client, setup_generation_data):
    # Mock first call malformed JSON, second call valid JSON
    malformed_response = MagicMock()
    malformed_response.json.return_value = {
        "choices": [{"message": {"content": 'I am an AI. Here is your output: {"invalid"}'}}]
    }
    
    valid_response = MagicMock()
    valid_response.json.return_value = {
        "choices": [{"message": {"content": '{"items": [{"question": "Q?", "answer": "A"}]}'}}]
    }
    
    mock_post.side_effect = [malformed_response, valid_response]

    mock_collection = MagicMock()
    mock_collection.insert_one.return_value = MagicMock(inserted_id="mongo456")
    mock_get_collection.return_value = mock_collection

    response = test_client.post(f"/api/v1/selections/{setup_generation_data['selection1']}/generate")
    
    assert response.status_code == 200
    assert mock_post.call_count == 2
    data = response.json()
    assert len(data["items"]) == 1

def test_generate_qa_selection_not_found(test_client):
    response = test_client.post("/api/v1/selections/999/generate")
    assert response.status_code == 404
