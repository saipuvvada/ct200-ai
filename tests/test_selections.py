import pytest
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
def setup_selection_data(db_session: Session):
    doc1 = Document(filename="CT-200", version="1")
    doc2 = Document(filename="CT-300", version="1")
    db_session.add(doc1)
    db_session.add(doc2)
    db_session.commit()

    n1 = Node(logical_node_id="l1", document_id=doc1.id, heading="Intro", level=1, order_index=1, content_hash="h1", node_type="heading")
    n2 = Node(logical_node_id="l2", document_id=doc1.id, body="Body", level=1, order_index=2, content_hash="h2", node_type="paragraph")
    n3 = Node(logical_node_id="l3", document_id=doc2.id, heading="Other", level=1, order_index=1, content_hash="h3", node_type="heading")
    
    db_session.add(n1)
    db_session.add(n2)
    db_session.add(n3)
    db_session.commit()

    return {"doc1": doc1.id, "doc2": doc2.id, "n1": n1.id, "n2": n2.id, "n3": n3.id}

def test_create_selection_success(test_client, setup_selection_data):
    payload = {
        "name": "My Selection",
        "document_id": setup_selection_data["doc1"],
        "node_ids": [setup_selection_data["n1"], setup_selection_data["n2"]]
    }
    response = test_client.post("/api/v1/selections", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Selection"
    assert data["document_id"] == setup_selection_data["doc1"]
    assert len(data["items"]) == 2

def test_create_selection_duplicate_nodes(test_client, setup_selection_data):
    # Should deduplicate transparently
    payload = {
        "name": "Dup Selection",
        "document_id": setup_selection_data["doc1"],
        "node_ids": [setup_selection_data["n1"], setup_selection_data["n1"]]
    }
    response = test_client.post("/api/v1/selections", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert len(data["items"]) == 1

def test_create_selection_invalid_document(test_client, setup_selection_data):
    payload = {
        "name": "Bad Doc",
        "document_id": 9999,
        "node_ids": [setup_selection_data["n1"]]
    }
    response = test_client.post("/api/v1/selections", json=payload)
    assert response.status_code == 404

def test_create_selection_missing_node(test_client, setup_selection_data):
    payload = {
        "name": "Bad Node",
        "document_id": setup_selection_data["doc1"],
        "node_ids": [9999]
    }
    response = test_client.post("/api/v1/selections", json=payload)
    assert response.status_code == 400
    assert "do not exist" in response.json()["detail"]

def test_create_selection_wrong_document_node(test_client, setup_selection_data):
    payload = {
        "name": "Wrong Doc Node",
        "document_id": setup_selection_data["doc1"],
        "node_ids": [setup_selection_data["n3"]] # n3 belongs to doc2
    }
    response = test_client.post("/api/v1/selections", json=payload)
    assert response.status_code == 400
    assert "does not belong to document" in response.json()["detail"]

def test_get_selections(test_client, setup_selection_data):
    payload = {
        "name": "My Selection 1",
        "document_id": setup_selection_data["doc1"],
        "node_ids": [setup_selection_data["n1"]]
    }
    test_client.post("/api/v1/selections", json=payload)
    
    response = test_client.get("/api/v1/selections")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["name"] == "My Selection 1"

def test_get_selection_by_id(test_client, setup_selection_data):
    payload = {
        "name": "My Selection 2",
        "document_id": setup_selection_data["doc1"],
        "node_ids": [setup_selection_data["n2"]]
    }
    create_response = test_client.post("/api/v1/selections", json=payload)
    selection_id = create_response.json()["id"]
    
    response = test_client.get(f"/api/v1/selections/{selection_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == selection_id
    assert len(data["items"]) == 1

def test_delete_selection(test_client, setup_selection_data):
    payload = {
        "name": "To Delete",
        "document_id": setup_selection_data["doc1"],
        "node_ids": [setup_selection_data["n1"]]
    }
    create_response = test_client.post("/api/v1/selections", json=payload)
    selection_id = create_response.json()["id"]
    
    del_response = test_client.delete(f"/api/v1/selections/{selection_id}")
    assert del_response.status_code == 204
    
    get_response = test_client.get(f"/api/v1/selections/{selection_id}")
    assert get_response.status_code == 404
