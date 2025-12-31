# Shiplight

A Python project with ChromaDB vector database and ACL-based permission filtering for semantic search.

## Features

- **Semantic Search** - Find documents by meaning, not just keywords
- **ACL-based Permissions** - Resource-centric access control
- **Two Search Methods** - `filter_first` and `query_first` strategies
- **Database Management** - Initialize, add, update, upsert, delete documents

## Quick Start

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

## Project Structure

```
shiplight/
├── config/
│   └── acl.json              # Access Control List configuration
├── resources/
│   ├── testfile1.txt         # Sample resource files
│   └── testfile2.txt
├── src/
│   └── __init__.py
├── tests/
│   └── test_search_engine.py # Unit tests (19 tests)
├── db_update.py              # Database management module
├── search_engine.py          # Search engine with ACL filtering
├── requirements.txt          # Dependencies
└── README.md
```

## Usage

### Architecture

**Important**: The database must be initialized by `DBManager` before using `SearchEngine` for queries.

- **DBManager**: Responsible for initializing and updating the vector database
- **SearchEngine**: Responsible for querying/searching the database (read-only operations)

### Database Management (Initialization & Updates)

```python
from db_update import DBManager

# Initialize database (first time or full rebuild)
db = DBManager()
db.init_db()

# Add new documents
db.update_db(
    ids=["doc1"],
    documents=["Content here"],
    operation="add"
)

# Update existing
db.update_db(
    ids=["doc1"],
    documents=["Updated content"],
    operation="update"
)

# Upsert (add or update)
db.update_db(
    ids=["doc1", "doc2"],
    documents=["Content 1", "Content 2"],
    operation="upsert"
)

# Delete
db.delete_documents(["doc1"])
```

### Search Engine (Querying)

```python
from db_update import DBManager
from search_engine import SearchEngine

# Step 1: Initialize database (if not already done)
db = DBManager()
db.init_db()

# Step 2: Use SearchEngine to query
engine = SearchEngine(collection_name="resources_db")

# Search all documents
results = engine.search("test content")

# Search with user permission filtering
results = engine.search("test content", user_id="user1")

# Choose search method
results = engine.search("query", user_id="user1", method="filter_first")  # default
results = engine.search("query", user_id="user1", method="query_first")
```

### Search Methods

| Method | Description | Best For |
|--------|-------------|----------|
| `filter_first` | Filter by permissions, then search | Users with limited access |
| `query_first` | Search all, then filter results | Better relevance ranking |

### ACL Configuration

Resource-centric ACL in `config/acl.json`:

```json
{
  "resources": {
    "resources/testfile1.txt": {
      "user1": ["read", "write", "delete"],
      "user2": ["read"]
    },
    "resources/testfile2.txt": {
      "user2": ["read"]
    }
  },
  "users": {
    "user1": { "name": "User One", "role": "admin" },
    "user2": { "name": "User Two", "role": "viewer" }
  }
}
```

### Check Permissions

```python
# Check if user can perform action
can_read = engine.can_access("user1", "resources/testfile1.txt", "read")  # True
can_write = engine.can_access("user2", "resources/testfile1.txt", "write")  # False
```

## Production Roadmap

### 1. Core Search Functionality
- [x] Basic semantic search with ChromaDB
- [x] Stable data model with metadata support
- [ ] **Flexible Resource Abstraction**
  - [ ] Generic `Resource` object to represent any data type
  - [ ] Support for multiple content types (files, emails, Slack messages, etc.)
  - [ ] Pluggable adapters for different raw data sources

```python
# Target abstraction
class Resource:
    id: str
    content: str
    source_type: str  # "file", "email", "slack", "document"
    metadata: dict    # source-specific metadata
    permissions: dict
```

### 2. Scalability & Performance
- [ ] **High QPS Support**
  - [ ] Connection pooling for database clients
  - [ ] Async/concurrent query handling
  - [ ] Query result caching layer
- [ ] **Database Optimization**
  - [ ] Evaluate persistent storage (ChromaDB with persistence, Pinecone, Qdrant)
  - [ ] Index optimization and sharding strategy
  - [ ] Follow vector DB best practices for production workloads

### 3. Data Ingestion Pipeline
- [ ] **ETL Pipeline: Raw Data → Vector DB**
  - [ ] Data connectors for various sources
  - [ ] Batch ingestion for bulk data
  - [ ] Real-time/streaming ingestion
  - [ ] Data validation and transformation
  - [ ] Incremental updates (upsert support) ✓ implemented

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Raw Sources │ -> │ Connectors  │ -> │ Transform   │ -> │ Vector DB   │
│ (file,email)│    │ (adapters)  │    │ (embed,meta)│    │ (ChromaDB)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 4. Engineering Excellence (EE)
- [x] **Unit Testing**
  - [x] Core search functionality tests (19 tests)
  - [x] Permission filtering tests
  - [x] Search method comparison tests
  - [ ] Integration tests
  - [ ] Load/performance tests
- [ ] **Logging**
  - [ ] Structured logging (JSON format)
  - [ ] Request/response logging
  - [ ] Error tracking and alerting
- [ ] **Metrics & Monitoring**
  - [ ] Query latency metrics
  - [ ] QPS monitoring
  - [ ] Error rate tracking
  - [ ] Database health metrics

### 5. Customer Integration
- [x] **ACL System**
  - [x] Resource-centric permission model
  - [x] User-based access filtering
  - [x] Permission check API (`can_access`)
  - [ ] Role-based access control (RBAC)
  - [ ] Integration with external identity providers (OAuth, SAML)
  - [ ] Audit logging for access events

---

## Dependencies

- `chromadb` - Vector database
- `python-dotenv` - Environment configuration
- `pytest` - Testing framework

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_search_engine.py::TestSearchEngine::test_search_as_user1 -v
```
