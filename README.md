# CT-200 Document Intelligence & QA Test Generation System

CT-200 Document Intelligence & QA Test Generation System is a professional, production-grade backend API built to parse CT-200 manuals, maintain version hierarchy, track changes, logical node matches, selection pinning, and generate QA test cases using LLM integration (Groq/Gemini).

---

## Assignment Mapping

| Assignment Requirement | Status |
| :--- | :--- |
| OCR Parsing | ✅ |
| Hierarchy Reconstruction | ✅ |
| Versioning | ✅ |
| Browse API | ✅ |
| Search | ✅ |
| Change Detection | ✅ |
| Selection API | ✅ |
| LLM Generation | ⏳ |
| Staleness Detection | ⏳ |

---

## Architecture Overview

```text
       CT-200 PDF
           │
           ▼
PDF Parser (pdfplumber + OCR)
           │
           ▼
   Hierarchy Builder
           │
           ▼
        SQLite
    (Document Tree)
           │
           ▼
    Version Matcher
           │
           ▼
       Browse API
           │
      ┌────┴───────┐
      ▼            ▼
  Selections     Search
      │
      ▼
 LLM Generator
      │
      ▼
   MongoDB
      │
      ▼
 Retrieval API
      │
      ▼
Staleness Detection
```

---

## Features

✓ OCR extraction
✓ Hierarchy reconstruction
✓ SHA256 hashing
✓ Logical node matching
✓ Browse API
✓ Search API
✓ Version comparison
✓ Selection pinning
✓ LLM QA generation
✓ Staleness detection

---

## Tech Stack
- **Python**: 3.12
- **Framework**: FastAPI (Pydantic v2)
- **Database**: SQLite (SQLAlchemy 2.0 ORM) & MongoDB (Atlas)
- **OCR & Document Extraction**: pdfplumber, pytesseract, Pillow
- **String Matching & Search**: RapidFuzz, difflib
- **Test Framework**: pytest, httpx

---

## Folder Structure
```text
ct200-ai/
├── app/
│   ├── api/          # FastAPI routers and endpoints
│   ├── models/       # SQLAlchemy relational database models
│   ├── schemas/      # Pydantic request/response validation schemas
│   ├── database/     # SQLAlchemy engine setup and dependencies
│   ├── services/     # Business logic layer
│   ├── parser/       # pdfplumber/tesseract extractor
│   ├── llm/          # Groq/Gemini integrations
│   ├── utils/        # Hash normalize, compare utilities
│   ├── config.py     # Configuration variables loader
│   └── main.py       # Application bootstrap
├── tests/            # pytest suite
└── data/             # Persistent storage directory
```

---

## Installation & Setup

1. **Clone and Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   ```
   **Example `.env`**:
   ```env
   DATABASE_URL=sqlite:///./ct200.db
   MONGODB_URI=...
   GROQ_API_KEY=...
   GEMINI_API_KEY=...
   OCR_LANGUAGE=eng
   LOG_LEVEL=INFO
   ```

3. **Initialize Database**:
   ```bash
   python -m app.database.init_db
   ```
   *(or `alembic upgrade head` if using Alembic)*

4. **Start the local API development server**:
   ```bash
   python app/main.py
   ```
   Or using Uvicorn:
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Verify the Health Check**:
   Visit [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health) or check the OpenAPI documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

---

## Running Tests

Execute the test suite using pytest:
```bash
pytest
pytest tests/
pytest --cov=app
```
**Current coverage**:
- 11 parser tests
- Browse API tests
- Version matching tests

---

## Re-ingesting a New Manual

```text
POST /api/v1/documents/upload
Upload ct200_manual.pdf
       ↓
   Version 1

Upload ct200_manual_v2.pdf
       ↓
   Version 2
       ↓
Run GET /node/{id}/changes
       ↓
Observe modified / added / removed
```

---

## Versioning Workflow

1. Upload CT200 v1.
2. Parser extracts hierarchy.
3. Nodes are stored.
4. Upload CT200 v2.
5. Matching algorithm compares:
   - Heading similarity
   - Parent context
   - Body similarity
6. Matching nodes inherit the same `logical_node_id`.
7. Changed hashes are marked as modified.
8. Retrieval API reports stale generations.

---

## API Reference

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| GET | `/documents` | List manuals |
| GET | `/sections` | Top sections |
| GET | `/node/{id}` | Node tree |
| GET | `/search` | Search |
| GET | `/changes` | Compare versions |

---

## API Examples (Browse API)

**1. List Documents**
```bash
curl -X 'GET' 'http://127.0.0.1:8000/api/v1/documents' -H 'accept: application/json'
```

**2. List Top-Level Sections**
```bash
curl -X 'GET' 'http://127.0.0.1:8000/api/v1/documents/1/sections?version=latest' -H 'accept: application/json'
```

**3. Get Node Details (Recursive Tree)**
```bash
curl -X 'GET' 'http://127.0.0.1:8000/api/v1/node/5' -H 'accept: application/json'
```

**4. Search nodes**
```bash
curl -X 'GET' 'http://127.0.0.1:8000/api/v1/search?query=battery&heading_only=false' -H 'accept: application/json'
```

**5. Get Node Version Changes**
```bash
curl -X 'GET' 'http://127.0.0.1:8000/api/v1/node/5/changes' -H 'accept: application/json'
```

## API Examples (Selection API)

**1. Create a Selection**
```bash
curl -X 'POST' 'http://127.0.0.1:8000/api/v1/selections' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "Important Battery Nodes",
  "document_id": 1,
  "node_ids": [5, 6, 8]
}'
```

**2. List All Selections**
```bash
curl -X 'GET' 'http://127.0.0.1:8000/api/v1/selections' -H 'accept: application/json'
```

**3. Delete a Selection**
```bash
curl -X 'DELETE' 'http://127.0.0.1:8000/api/v1/selections/1'
```

---

## Known Limitations

- Designed specifically for CT-200 manuals.
- OCR accuracy depends on scan quality.
- Version matching uses heuristic scoring.
- Large document restructuring may reduce matching accuracy.

---

## Future Improvements

- Semantic node matching using embeddings
- Elasticsearch search
- Async PDF ingestion
- Background jobs using Celery
- Automatic stale regeneration
- Better OCR layout detection
- Docker deployment
