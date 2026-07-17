# CT-200 Document Intelligence & QA Test Generation System

CT-200 Document Intelligence & QA Test Generation System is a professional, production-grade backend API built to parse CT-200 manuals, maintain version hierarchy, track changes, logical node matches, selection pinning, and generate QA test cases using LLM integration (Groq/Gemini).

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

2. **Configure environment settings**:
   Copy `.env.example` to `.env` and fill out your keys:
   ```bash
   cp .env.example .env
   ```

3. **Start the local API development server**:
   ```bash
   python app/main.py
   ```
   Or using Uvicorn:
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Verify the Health Check**:
   Visit [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health) or check the OpenAPI documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
