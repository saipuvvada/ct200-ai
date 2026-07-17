import pytest
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
def setup_browse_data(db_session: Session):
    doc1 = Document(filename="CT-200", version="1")
    doc2 = Document(filename="CT-200", version="2")
    db_session.add(doc1)
    db_session.add(doc2)
    db_session.commit()

    # Doc 1 Nodes
    n1 = Node(logical_node_id="l1", document_id=doc1.id, heading="Intro", level=1, order_index=1, content_hash="h1", node_type="heading")
    db_session.add(n1)
    db_session.commit()

    n2 = Node(logical_node_id="l2", document_id=doc1.id, parent_id=n1.id, body="Old Body", level=2, order_index=2, content_hash="h2", node_type="paragraph")
    db_session.add(n2)
    db_session.commit()

    # Doc 2 Nodes
    n3 = Node(logical_node_id="l1", document_id=doc2.id, heading="Intro", level=1, order_index=1, content_hash="h1", node_type="heading")
    db_session.add(n3)
    db_session.commit()

    # Node 2 modified in v2
    n4 = Node(logical_node_id="l2", document_id=doc2.id, parent_id=n3.id, body="New Body", level=2, order_index=2, content_hash="h2_new", node_type="paragraph")
    db_session.add(n4)
    db_session.commit()

    return {"doc1": doc1.id, "doc2": doc2.id, "n1": n1.id, "n2": n2.id, "n3": n3.id, "n4": n4.id}

def test_list_documents(test_client, setup_browse_data):
    response = test_client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert "total_nodes" in data[0]

def test_get_sections(test_client, setup_browse_data):
    doc_id = setup_browse_data["doc1"]
    response = test_client.get(f"/api/v1/documents/{doc_id}/sections")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["heading"] == "Intro"
    assert data[0]["has_children"] is True

def test_get_sections_with_version(test_client, setup_browse_data):
    doc_id = setup_browse_data["doc1"]
    response = test_client.get(f"/api/v1/documents/{doc_id}/sections?version=latest")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["heading"] == "Intro"

def test_get_node_recursive(test_client, setup_browse_data):
    node_id = setup_browse_data["n1"]
    response = test_client.get(f"/api/v1/node/{node_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["heading"] == "Intro"
    assert "children" in data
    assert len(data["children"]) == 1
    assert data["children"][0]["body"] == "Old Body"

def test_search_heading(test_client, setup_browse_data):
    response = test_client.get("/api/v1/search?query=Intro")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Found in both documents

def test_search_body(test_client, setup_browse_data):
    response = test_client.get("/api/v1/search?query=New Body")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["node_id"] == setup_browse_data["n4"]

def test_search_no_results(test_client, setup_browse_data):
    response = test_client.get("/api/v1/search?query=NonExistent")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0

def test_compare_unchanged_node(test_client, setup_browse_data):
    node_id = setup_browse_data["n3"] # Intro node in doc 2 (same as doc 1)
    response = test_client.get(f"/api/v1/node/{node_id}/changes")
    assert response.status_code == 200
    data = response.json()
    assert data["changed"] is False

def test_compare_modified_node(test_client, setup_browse_data):
    node_id = setup_browse_data["n4"] # Modified node in doc 2
    response = test_client.get(f"/api/v1/node/{node_id}/changes")
    assert response.status_code == 200
    data = response.json()
    assert data["changed"] is True
    assert data["change_type"] == "modified"
    assert data["diff_summary"]["body_changed"] is True
    assert data["diff_summary"]["heading_changed"] is False

def test_invalid_node_404(test_client, setup_browse_data):
    response = test_client.get("/api/v1/node/9999")
    assert response.status_code == 404
