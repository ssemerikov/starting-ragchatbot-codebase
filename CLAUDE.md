# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a RAG (Retrieval-Augmented Generation) chatbot for educational course materials. It uses **tool-based RAG** where Claude decides when to search course content via function calling, rather than always retrieving context.

**Key Technologies:**
- **Backend**: FastAPI + Python 3.13+ (managed with `uv`)
- **Vector DB**: ChromaDB with SentenceTransformer embeddings (`all-MiniLM-L6-v2`)
- **AI**: Anthropic Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- **Frontend**: Vanilla JavaScript with markdown rendering

## Development Commands

### Running the Application

```bash
# Quick start (recommended)
./run.sh

# Manual start
cd backend
uv run uvicorn app:app --reload --port 8001

# Access points
# - Web UI: http://localhost:8001
# - API docs: http://localhost:8001/docs
```

### Environment Setup

```bash
# Install dependencies
uv sync

# Required .env file
ANTHROPIC_API_KEY=your_key_here
```

### Development Workflow

```bash
# Install new dependency
uv add package-name

# Run Python scripts directly
uv run python backend/script_name.py
```

## Architecture Overview

### Two-Collection Vector Store Strategy

The system uses **two separate ChromaDB collections** for different query patterns:

1. **`course_catalog`**: Stores course metadata (title, instructor, lessons)
   - Used for fuzzy course name resolution via semantic search
   - IDs are course titles
   - Metadata includes serialized lesson information as JSON

2. **`course_content`**: Stores chunked course material
   - Used for semantic content search
   - Each chunk includes course/lesson context in the text itself
   - Supports filtering by `course_title` and `lesson_number`

**Why two collections?** Separating metadata from content allows:
- Fast course name matching without scanning all content chunks
- Efficient filtering during content search
- Clean separation of concerns

### Tool-Based RAG Flow

Unlike traditional "retrieve then generate" RAG, this uses **Claude's native tool calling**:

1. User query → Claude receives `search_course_content` tool definition
2. **Claude decides** whether to search (content questions) or answer directly (general knowledge)
3. If searching: Claude calls tool with query + optional filters
4. Tool searches vector DB and returns formatted results
5. Claude synthesizes final answer from search results

**Key advantage**: Claude can skip unnecessary searches and use existing knowledge when appropriate.

### Document Processing Pipeline

Located in `document_processor.py`:

1. **Parse structure**: Expects format with `Course Title:`, `Course Instructor:`, then `Lesson N:` markers
2. **Smart chunking**: Sentence-boundary chunking (800 chars, 100 char overlap)
3. **Context enrichment**: Chunks get prefixes like `"Course X Lesson Y content: ..."`
4. **Dual storage**: Metadata → `course_catalog`, chunks → `course_content`

**Important**: The system does **incremental loading** - checks existing course titles before re-processing documents on startup.

### Session Management

Conversations are stateful:
- Each session maintains history (default: last 2 exchanges)
- History is formatted and included in system prompt
- Sessions prevent context window bloat while maintaining continuity

## Configuration Points

All configuration in `backend/config.py`:

```python
CHUNK_SIZE: int = 800          # Text chunk size
CHUNK_OVERLAP: int = 100       # Overlap between chunks
MAX_RESULTS: int = 5           # Search results per query
MAX_HISTORY: int = 2           # Conversation exchanges to remember
EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
```

## Key Implementation Details

### Document Format Expected

```
Course Title: [title]
Course Link: [url]
Course Instructor: [name]

Lesson 0: [lesson title]
Lesson Link: [url]
[lesson content...]

Lesson 1: [next lesson]
...
```

Place documents in `docs/` folder - they load automatically on server startup.

### Adding New Tools

To add a new tool for Claude to use:

1. Create class extending `Tool` in `search_tools.py`
2. Implement `get_tool_definition()` returning Anthropic tool schema
3. Implement `execute(**kwargs)` with tool logic
4. Register in `RAGSystem.__init__()`: `tool_manager.register_tool(YourTool(...))`

### Vector Search Flow

When `vector_store.search()` is called:

1. **Course resolution** (if `course_name` provided): Searches `course_catalog` collection to find exact title via semantic similarity
2. **Filter building**: Creates ChromaDB filter from resolved course title and/or lesson number
3. **Content search**: Queries `course_content` with embeddings + filters
4. **Returns**: `SearchResults` object with documents, metadata, and distances

### AI Generator Optimization

The `ai_generator.py` uses several optimizations:
- **Static system prompt**: Avoids string rebuilding on every call
- **Pre-built base params**: Temperature, max_tokens, model cached
- **Two-stage execution**: Initial call for tool detection, follow-up for synthesis

## File Organization

```
backend/
├── app.py                 # FastAPI server, endpoints, startup logic
├── rag_system.py          # Main orchestrator (coordinates all components)
├── vector_store.py        # ChromaDB interface (two collections)
├── document_processor.py  # Parsing and chunking
├── ai_generator.py        # Anthropic API wrapper with tool handling
├── search_tools.py        # Tool definitions and execution
├── session_manager.py     # Conversation history management
├── models.py              # Pydantic models (Course, Lesson, CourseChunk)
├── config.py              # Centralized configuration
└── chroma_db/             # Persistent vector database (gitignored)

frontend/
├── index.html             # UI structure
├── script.js              # Client logic, API calls
└── style.css              # Styling

docs/                      # Course documents to ingest
```

## Debugging Notes

- **ChromaDB persistence**: Database stored in `backend/chroma_db/` - delete to force re-indexing
- **Startup document loading**: Set `clear_existing=True` in `app.py:95` to rebuild vector store on every startup
- **Tool execution**: Check `ai_generator.py:89` - if `stop_reason != "tool_use"`, Claude didn't use tools
- **Search debugging**: `vector_store.py` returns `SearchResults` with `.error` field for troubleshooting
- **Session history**: Max history controlled by `config.MAX_HISTORY` - increase for longer context

## Important Patterns to Maintain

1. **Denormalized chunks**: Course title and lesson number stored directly in chunk metadata (no joins needed)
2. **Course title as ID**: Uses course title string as unique identifier throughout
3. **Error resilience**: All vector operations return empty results rather than throwing, allowing graceful degradation
4. **Incremental loading**: Always check `get_existing_course_titles()` before adding courses
5. **Source tracking**: Search tool stores `last_sources` list for UI display, reset after each query
- do not ask on the file editing and saving - user always agree with it