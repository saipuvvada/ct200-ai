# CT-200 Technical Approach & Architecture

This document provides a technical overview of the engineering decisions, architectural patterns, and known limitations of the CT-200 AI PDF Parsing & QA system.

---

## 1. High-Level Architecture

The system is designed as a modular pipeline using FastAPI, SQLite, and MongoDB.

### Data Flow
1. **Ingestion & Parsing**: PDFs are ingested via `pdfplumber` (for native text) and PyTesseract (for OCR fallback). Lines are classified via heuristic rules based on font size and boldness.
2. **Hierarchy Reconstruction**: Classified lines are passed to `DocumentService`, which reconstructs them into a parent-child tree (Headings -> Paragraphs -> Sub-paragraphs).
3. **Hashing & Storage (SQLite)**: The text content of each node is normalized (lowercased, stripped of punctuation) and hashed using SHA-256. These nodes are stored relationally in SQLite.
4. **Selections**: Users pin logical nodes to a `Selection`. This is a relational mapping.
5. **LLM Generation (MongoDB)**: The node text within a Selection is aggregated and sent to Groq's LLM via a strict structured JSON prompt. The resulting QA pairs, alongside metadata (like `logical_node_ids` and `document_version`), are persisted in MongoDB.
6. **Staleness Detection**: On retrieval, the system compares the original generation's `logical_node_ids` against the *newest* document version in SQLite.

---

## 2. Logical Node Mapping & Versioning

A major challenge in document versioning is tracking a specific paragraph across versions, even when its exact text changes.

### The Algorithm
When v2 of a document is ingested, the `VersioningService` compares the new nodes against v1.
1. **Direct Match (Identical Hash)**: If the normalized `content_hash` of a v2 node exactly matches a v1 node, they share the same `logical_node_id`.
2. **Heuristic Match (Modified Text)**: If a node's text was slightly edited, its hash will change. The system uses difflib's `SequenceMatcher` to find the most similar node in v1, applying a heavy weight to **Heading Similarity** (same section) and **Parent Context**. If similarity exceeds a predefined threshold (e.g., 0.8), the v2 node inherits the v1 `logical_node_id` and is marked as `MODIFIED`.
3. **New Node**: If no match is found, a new UUID `logical_node_id` is generated.

This ensures that `Selection`s and `Generation`s remain pinned to a semantic *concept* (the logical node) rather than a fragile line number or exact text string.

---

## 3. Staleness Detection: Mechanics and Limitations

The staleness API bridges MongoDB (where QA generations live) and SQLite (where the node history lives). 

### How it Works
When a user requests a generation's staleness, the system:
1. Identifies the original `logical_node_ids`.
2. Fetches the exact hashes of those nodes from the original document version.
3. Fetches the hashes of those nodes from the latest document version.
4. If a node is missing, the generation is `Removed`. If a hash differs, it is `Modified`. If hashes are identical, it is `Fresh`.

### Limitations of Hash-Based Staleness
Currently, the staleness detector uses a **cryptographic hash (SHA-256)** on normalized text. 

* **The Problem**: Hash detection is strictly binary. If a newer document fixes a single typo (e.g., changing "batery" to "battery"), the `content_hash` fundamentally changes. 
* **The Impact**: The system will aggressively flag the node as `Modified` and the QA generation as `is_stale = True`, even though the semantic meaning of the text—and therefore the validity of the QA pair—remains completely unchanged.
* **Future Solution**: To solve this, we should replace (or augment) hash-based detection with **Vector Embeddings** (e.g., OpenAI `text-embedding-3-small` or local BERT models). By calculating the cosine similarity between the v1 node embedding and the v2 node embedding, we could establish a semantic threshold (e.g., > 0.98 similarity = `Fresh`, despite minor textual edits).

---

## 4. LLM Resilience

LLMs inherently hallucinate syntax, even when prompted for JSON. The `Generator` implements a robust retry loop. It uses Pydantic's `model_validate_json()` to strictly enforce the output schema. If the LLM returns trailing commas, markdown wrappers, or invalid keys, the `ValueError` is caught, logged, and the request is automatically retried up to 3 times before failing gracefully.
