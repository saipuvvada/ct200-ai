import pytest
from unittest.mock import patch, MagicMock
from bson.objectid import ObjectId
from fastapi.testclient import TestClient
from app.main import app
from app.models.document import Document
from app.models.node import Node
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
def setup_staleness_data(db_session: Session):
    doc_v1 = Document(filename="CT-200", version="1")
    db_session.add(doc_v1)
    db_session.commit()

    n1_v1 = Node(logical_node_id="l1", document_id=doc_v1.id, content_hash="hash_a", node_type="heading", order_index=1, level=1)
    n2_v1 = Node(logical_node_id="l2", document_id=doc_v1.id, content_hash="hash_b", node_type="paragraph", order_index=2, level=1)
    n3_v1 = Node(logical_node_id="l3", document_id=doc_v1.id, content_hash="hash_c", node_type="paragraph", order_index=3, level=1)
    
    db_session.add_all([n1_v1, n2_v1, n3_v1])
    db_session.commit()

    # Create a newer version where l1 is unchanged, l2 is modified, l3 is removed, l4 is added
    doc_v2 = Document(filename="CT-200", version="2")
    db_session.add(doc_v2)
    db_session.commit()

    n1_v2 = Node(logical_node_id="l1", document_id=doc_v2.id, content_hash="hash_a", node_type="heading", order_index=1, level=1)
    n2_v2 = Node(logical_node_id="l2", document_id=doc_v2.id, content_hash="hash_b_modified", node_type="paragraph", order_index=2, level=1)
    n4_v2 = Node(logical_node_id="l4", document_id=doc_v2.id, content_hash="hash_d", node_type="paragraph", order_index=3, level=1)

    db_session.add_all([n1_v2, n2_v2, n4_v2])
    db_session.commit()

    return {
        "doc_v1": doc_v1.id,
        "doc_v2": doc_v2.id,
    }

@patch("app.services.staleness_service.get_generations_collection")
def test_staleness_fresh(mock_get_collection, test_client, setup_staleness_data):
    gen_id = str(ObjectId())
    
    # Mock Mongo returning a generation against v2 directly
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {
        "_id": ObjectId(gen_id),
        "document_id": setup_staleness_data["doc_v2"],
        "document_version": "2",
        "logical_node_ids": ["l1", "l2"],
        "status": "fresh"
    }
    mock_get_collection.return_value = mock_collection

    response = test_client.get(f"/api/v1/generations/{gen_id}/staleness")
    assert response.status_code == 200
    data = response.json()
    assert data["is_stale"] is False
    assert data["overall_status"] == "Fresh"

@patch("app.services.staleness_service.get_generations_collection")
def test_staleness_modified(mock_get_collection, test_client, setup_staleness_data):
    gen_id = str(ObjectId())
    
    # Mock Mongo returning a generation against v1, but l2 was modified in v2
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {
        "_id": ObjectId(gen_id),
        "document_id": setup_staleness_data["doc_v1"],
        "document_version": "1",
        "logical_node_ids": ["l1", "l2"],
        "status": "fresh"
    }
    mock_get_collection.return_value = mock_collection

    response = test_client.get(f"/api/v1/generations/{gen_id}/staleness")
    assert response.status_code == 200
    data = response.json()
    assert data["is_stale"] is True
    assert data["overall_status"] == "Modified"
    
    nodes = data["node_details"]
    l1_node = next(n for n in nodes if n["logical_node_id"] == "l1")
    l2_node = next(n for n in nodes if n["logical_node_id"] == "l2")
    
    assert l1_node["status"] == "Fresh"
    assert l2_node["status"] == "Modified"
    assert l2_node["old_hash"] == "hash_b"
    assert l2_node["new_hash"] == "hash_b_modified"

@patch("app.services.staleness_service.get_generations_collection")
def test_staleness_removed(mock_get_collection, test_client, setup_staleness_data):
    gen_id = str(ObjectId())
    
    # Mock Mongo returning a generation against v1, where l3 was removed in v2
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = {
        "_id": ObjectId(gen_id),
        "document_id": setup_staleness_data["doc_v1"],
        "document_version": "1",
        "logical_node_ids": ["l1", "l3"],
        "status": "fresh"
    }
    mock_get_collection.return_value = mock_collection

    response = test_client.get(f"/api/v1/generations/{gen_id}/staleness")
    assert response.status_code == 200
    data = response.json()
    assert data["is_stale"] is True
    assert data["overall_status"] == "Removed"
    
    nodes = data["node_details"]
    l3_node = next(n for n in nodes if n["logical_node_id"] == "l3")
    
    assert l3_node["status"] == "Removed"
    assert l3_node["new_hash"] is None
