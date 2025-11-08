# Architecture Flow Diagrams

This document contains detailed flow diagrams for understanding how the RAG chatbot processes data and handles queries.

## Table of Contents
- [Document Loading Flow](#document-loading-flow)
- [User Query Flow](#user-query-flow)
- [Vector Search Details](#vector-search-details)
- [Tool Execution Flow](#tool-execution-flow)

---

## Document Loading Flow

This diagram shows how course documents are processed and loaded into the vector database on server startup.

```
┌─────────────────────────────────────────────────────────────────┐
│ SERVER STARTUP                                                  │
│ app.py:88-98 (@app.on_event("startup"))                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    docs_path = "../docs"
                             │
                             ▼
        rag_system.add_course_folder(docs_path, clear_existing=False)
                             │
┌────────────────────────────┴────────────────────────────────────┐
│ RAG SYSTEM                                                      │
│ rag_system.py:52-100                                           │
└─────────────────────────────────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ clear_existing? │
                    │ (False default) │
                    └────────┬────────┘
                             │ No
                             ▼
              Get existing course titles from DB
              existing_titles = vector_store.get_existing_course_titles()
                             │
                    ┌────────▼────────┐
                    │ For each file   │
                    │ in docs/ folder │
                    │ (.txt/.pdf/     │
                    │  .docx)         │
                    └────────┬────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│ DOCUMENT PROCESSOR                                              │
│ document_processor.py:97-259                                   │
└─────────────────────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
   Read File          Extract Metadata      Parse Lessons
  (lines 13-21)        (lines 110-146)      (lines 156-243)
        │                    │                    │
        │              ┌─────┴─────┐              │
        │              │ Regex:    │              │
        │              │ - Course  │              │
        │              │   Title:  │              │
        │              │ - Course  │              │
        │              │   Link:   │              │
        │              │ - Course  │              │
        │              │   Instructor:            │
        │              └─────┬─────┘              │
        │                    │                    │
        │                    │         ┌──────────▼──────────┐
        │                    │         │ For each lesson:    │
        │                    │         │ Regex pattern:      │
        │                    │         │ Lesson \d+: (.+)    │
        │                    │         │                     │
        │                    │         │ Extract:            │
        │                    │         │ - lesson_number     │
        │                    │         │ - title             │
        │                    │         │ - link (optional)   │
        │                    │         │ - content (all text │
        │                    │         │   until next lesson)│
        │                    │         └──────────┬──────────┘
        │                    │                    │
        │                    │                    ▼
        │                    │         ┌──────────────────────┐
        │                    │         │ CHUNK TEXT           │
        │                    │         │ (lines 25-91)        │
        │                    │         ├──────────────────────┤
        │                    │         │ 1. Normalize spaces  │
        │                    │         │ 2. Split sentences   │
        │                    │         │    (regex on . ! ?)  │
        │                    │         │ 3. Build chunks:     │
        │                    │         │    - Start at 0 chars│
        │                    │         │    - Add sentences   │
        │                    │         │      until ~800 chars│
        │                    │         │    - Calculate overlap│
        │                    │         │      (100 chars back)│
        │                    │         │    - Next chunk starts│
        │                    │         │      with overlap    │
        │                    │         └──────────┬───────────┘
        │                    │                    │
        │                    │         ┌──────────▼───────────┐
        │                    │         │ ENRICH CHUNKS        │
        │                    │         │ (lines 184-243)      │
        │                    │         ├──────────────────────┤
        │                    │         │ Add context prefix:  │
        │                    │         │ "Course {title}      │
        │                    │         │  Lesson {num}        │
        │                    │         │  content: {chunk}"   │
        │                    │         └──────────┬───────────┘
        │                    │                    │
        │                    │         ┌──────────▼───────────┐
        │                    │         │ CREATE OBJECTS       │
        │                    │         ├──────────────────────┤
        │                    │         │ CourseChunk:         │
        │                    │         │ - content (enriched) │
        │                    │         │ - course_title       │
        │                    │         │ - lesson_number      │
        │                    │         │ - chunk_index        │
        │                    │         └──────────┬───────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                    ┌────────▼────────┐
                    │ Course object   │
                    │ CourseChunk[]   │
                    └────────┬────────┘
                             │
                    Return to RAG System
                             │
┌────────────────────────────┴────────────────────────────────────┐
│ CHECK IF NEW COURSE                                             │
│ rag_system.py:87-96                                            │
└─────────────────────────────────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ Is course.title │
                    │ in existing_    │
                    │ course_titles?  │
                    └────────┬────────┘
                        YES  │  NO
                    ┌────────┴────────┐
                    │                 │
                 SKIP              ADD TO DB
              (already              │
               exists)              │
                             ┌──────▼──────┐
                             │ VECTOR STORE│
                             └──────┬──────┘
                    ┌───────────────┴───────────────┐
                    │                               │
        ┌───────────▼──────────┐       ┌───────────▼──────────┐
        │ ADD COURSE METADATA  │       │ ADD COURSE CONTENT   │
        │ vector_store.py:     │       │ vector_store.py:     │
        │ 135-160              │       │ 162-180              │
        └───────────┬──────────┘       └───────────┬──────────┘
                    │                               │
        ┌───────────▼──────────┐       ┌───────────▼──────────┐
        │ COLLECTION:          │       │ COLLECTION:          │
        │ course_catalog       │       │ course_content       │
        ├──────────────────────┤       ├──────────────────────┤
        │ Documents:           │       │ Documents:           │
        │ [course.title]       │       │ [chunk.content,      │
        │                      │       │  chunk.content, ...] │
        │ Metadata:            │       │                      │
        │ {                    │       │ Metadata:            │
        │   title: "...",      │       │ [{                   │
        │   instructor: "...", │       │   course_title: "...",│
        │   course_link: "...",│       │   lesson_number: 1,  │
        │   lessons_json: "[...]",     │   chunk_index: 0     │
        │   lesson_count: 4    │       │ }, ...]              │
        │ }                    │       │                      │
        │                      │       │ IDs:                 │
        │ IDs:                 │       │ ["CourseName_0",     │
        │ [course.title]       │       │  "CourseName_1", ...]│
        └───────────┬──────────┘       └───────────┬──────────┘
                    │                               │
                    └───────────┬───────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │ SentenceTransformer   │
                    │ Creates embeddings    │
                    │ (all-MiniLM-L6-v2)    │
                    │ - 384 dimensions      │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ ChromaDB              │
                    │ Persistent Storage    │
                    │ (backend/chroma_db/)  │
                    │                       │
                    │ Stores:               │
                    │ - Documents (text)    │
                    │ - Embeddings (vectors)│
                    │ - Metadata (dict)     │
                    │ - IDs (strings)       │
                    └───────────────────────┘
```

**Key Points:**
- Documents load automatically on server startup
- Incremental loading: checks existing titles, skips duplicates
- Two separate collections for different purposes
- Chunks include context in the text itself ("Course X Lesson Y content: ...")
- Course title serves as unique identifier throughout

---

## User Query Flow

This diagram shows the complete flow of a user query from frontend to backend and back.

```
┌──────────────────────────────────────────────────────────────────┐
│ FRONTEND (Browser)                                               │
│ script.js                                                        │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    User types query and clicks Send
                    (script.js:45-96)
                             │
                             ▼
                    sendMessage() {
                      - Disable input
                      - Add user message to chat UI
                      - Show loading animation
                    }
                             │
                             ▼
                    POST /api/query
                    Content-Type: application/json

                    Body:
                    {
                      "query": "What is prompt caching?",
                      "session_id": "abc123" (or null for new)
                    }
                             │
                             ▼ HTTP Request
┌──────────────────────────────────────────────────────────────────┐
│ BACKEND - FASTAPI ENDPOINT                                       │
│ app.py:56-74                                                     │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    @app.post("/api/query")
                    async def query_documents(request: QueryRequest)
                             │
                             ├─► session_id provided?
                             │   NO → session_id = session_manager.create_session()
                             │   YES → use provided session_id
                             │
                             ▼
                    rag_system.query(request.query, session_id)
                             │
┌──────────────────────────┴───────────────────────────────────────┐
│ RAG SYSTEM                                                       │
│ rag_system.py:102-140                                           │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ├─► Get conversation history (if exists)
                             │   history = session_manager.get_conversation_history(session_id)
                             │   → Returns last N exchanges formatted as text
                             │
                             ├─► Get tool definitions
                             │   tools = tool_manager.get_tool_definitions()
                             │
                             ▼
                    ai_generator.generate_response(
                        query=prompt,
                        conversation_history=history,
                        tools=tools,
                        tool_manager=tool_manager
                    )
                             │
┌──────────────────────────┴───────────────────────────────────────┐
│ AI GENERATOR - FIRST CALL                                        │
│ ai_generator.py:43-87                                           │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ├─► Build system prompt
                             │   system_content = SYSTEM_PROMPT + conversation_history
                             │
                             ├─► Prepare API parameters
                             │   {
                             │     model: "claude-sonnet-4-20250514",
                             │     temperature: 0,
                             │     max_tokens: 800,
                             │     messages: [{"role": "user", "content": query}],
                             │     system: system_content,
                             │     tools: [search_course_content definition],
                             │     tool_choice: {"type": "auto"}
                             │   }
                             │
                             ▼
                    client.messages.create(**api_params)
                             │
                             ▼ API Call
┌──────────────────────────────────────────────────────────────────┐
│ ANTHROPIC CLAUDE API                                             │
└──────────────────────────────────────────────────────────────────┘
                             │
                    Claude analyzes the query:
                    "This is about course content → I should search"
                             │
                             ▼
                    Response:
                    stop_reason: "tool_use"
                    content: [{
                      type: "tool_use",
                      id: "toolu_123abc",
                      name: "search_course_content",
                      input: {
                        query: "prompt caching",
                        course_name: null,
                        lesson_number: null
                      }
                    }]
                             │
                             ▼ Back to AI Generator
┌──────────────────────────────────────────────────────────────────┐
│ AI GENERATOR - TOOL EXECUTION                                    │
│ ai_generator.py:89-135                                          │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ├─► Check: stop_reason == "tool_use"? YES
                             │
                             ▼
                    _handle_tool_execution(response, params, tool_manager)
                             │
                             ├─► For each tool_use block in response.content:
                             │
                             ▼
                    tool_manager.execute_tool(
                        name="search_course_content",
                        **{"query": "prompt caching", ...}
                    )
                             │
┌──────────────────────────┴───────────────────────────────────────┐
│ SEARCH TOOL                                                      │
│ search_tools.py:52-114                                          │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    CourseSearchTool.execute(
                        query="prompt caching",
                        course_name=None,
                        lesson_number=None
                    )
                             │
                             ▼
                    vector_store.search(
                        query="prompt caching",
                        course_name=None,
                        lesson_number=None
                    )
                             │
┌──────────────────────────┴───────────────────────────────────────┐
│ VECTOR STORE - SEARCH                                            │
│ vector_store.py:61-100                                          │
└──────────────────────────────────────────────────────────────────┘
                             │
                    Step 1: Resolve course name (if provided)
                             │
                             ├─► course_name provided? NO → skip
                             │   YES → Query course_catalog collection
                             │         to find exact title via semantic search
                             │
                    Step 2: Build filter dictionary
                             │
                             ├─► Build where clause:
                             │   course_title AND/OR lesson_number
                             │   (None in this example)
                             │
                    Step 3: Search course_content collection
                             │
                             ▼
                    course_content.query(
                        query_texts=["prompt caching"],
                        n_results=5,
                        where=None
                    )
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ CHROMADB                                                         │
└──────────────────────────────────────────────────────────────────┘
                             │
                    1. Embed query using SentenceTransformer
                       query_embedding = model.encode("prompt caching")
                       → 384-dim vector
                             │
                    2. Compute cosine similarity
                       for all stored chunk embeddings
                             │
                    3. Return top N results by similarity
                             │
                             ▼
                    Results:
                    {
                      documents: [[
                        "Course XYZ Lesson 3 content: Prompt caching...",
                        "Course ABC Lesson 2 content: Another mention..."
                      ]],
                      metadatas: [[
                        {course_title: "...", lesson_number: 3, chunk_index: 15},
                        {course_title: "...", lesson_number: 2, chunk_index: 8}
                      ]],
                      distances: [[0.12, 0.18, ...]]
                    }
                             │
                             ▼ Back to Vector Store
                    SearchResults.from_chroma(results)
                             │
                             ▼ Back to Search Tool
┌──────────────────────────────────────────────────────────────────┐
│ SEARCH TOOL - FORMAT RESULTS                                     │
│ search_tools.py:88-114                                          │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    _format_results(results)
                             │
                             ├─► For each (document, metadata):
                             │   - Extract course_title, lesson_number
                             │   - Build header: "[Course - Lesson N]"
                             │   - Track source: "Course - Lesson N"
                             │
                             ├─► Store sources in self.last_sources
                             │   (for UI display later)
                             │
                             ▼
                    Returns formatted string:

                    "[Building Towards Computer Use - Lesson 3]
                    Prompt caching retains some of the results...

                    [Another Course - Lesson 1]
                    Additional context about caching..."
                             │
                             ▼ Back to Tool Manager → AI Generator
┌──────────────────────────────────────────────────────────────────┐
│ AI GENERATOR - SECOND CALL                                       │
│ ai_generator.py:122-135                                         │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ├─► Build message history:
                             │   messages = [
                             │     {role: "user", content: "What is prompt caching?"},
                             │     {role: "assistant", content: [tool_use block]},
                             │     {role: "user", content: [{
                             │       type: "tool_result",
                             │       tool_use_id: "toolu_123abc",
                             │       content: "[formatted search results]"
                             │     }]}
                             │   ]
                             │
                             ▼
                    client.messages.create(
                        messages=messages,
                        system=system_prompt + history
                        // No tools in second call
                    )
                             │
                             ▼ API Call
┌──────────────────────────────────────────────────────────────────┐
│ ANTHROPIC CLAUDE API - SECOND CALL                               │
└──────────────────────────────────────────────────────────────────┘
                             │
                    Claude synthesizes answer from search results:

                    "Prompt caching is a feature that retains
                    some of the results of processing prompts
                    between invocations to the model, which can
                    be a large cost and latency saver..."
                             │
                             ▼
                    Response:
                    stop_reason: "end_turn"
                    content: [{
                      type: "text",
                      text: "[final synthesized answer]"
                    }]
                             │
                             ▼ Back to AI Generator → RAG System
┌──────────────────────────────────────────────────────────────────┐
│ RAG SYSTEM - FINALIZE                                            │
│ rag_system.py:129-140                                           │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ├─► Get sources from tool manager
                             │   sources = tool_manager.get_last_sources()
                             │   → ["Building Towards Computer Use - Lesson 3", ...]
                             │
                             ├─► Reset sources (cleanup)
                             │   tool_manager.reset_sources()
                             │
                             ├─► Update conversation history
                             │   session_manager.add_exchange(
                             │     session_id,
                             │     query="What is prompt caching?",
                             │     response="[final answer]"
                             │   )
                             │
                             ▼
                    return (response, sources)
                             │
                             ▼ Back to FastAPI endpoint
┌──────────────────────────────────────────────────────────────────┐
│ FASTAPI - BUILD RESPONSE                                         │
│ app.py:68-72                                                     │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    QueryResponse(
                        answer="Prompt caching is a feature...",
                        sources=["Building Towards Computer Use - Lesson 3", ...],
                        session_id="abc123"
                    )
                             │
                             ▼ HTTP Response (JSON)
┌──────────────────────────────────────────────────────────────────┐
│ FRONTEND - DISPLAY RESPONSE                                      │
│ script.js:76-95                                                  │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ├─► Update session_id if new
                             │   currentSessionId = data.session_id
                             │
                             ├─► Remove loading animation
                             │   loadingMessage.remove()
                             │
                             ├─► Render markdown to HTML
                             │   marked.parse(data.answer)
                             │
                             ▼
                    addMessage(data.answer, 'assistant', data.sources)
                             │
                             ▼
                    ┌────────────────────────────────┐
                    │ Chat UI displays:              │
                    │                                │
                    │ User: What is prompt caching?  │
                    │                                │
                    │ 🤖 Assistant:                  │
                    │ Prompt caching is a feature... │
                    │                                │
                    │ ▼ Sources                      │
                    │   Building Towards Computer    │
                    │   Use - Lesson 3               │
                    └────────────────────────────────┘
```

**Key Points:**
- Two API calls to Claude: first to decide tools, second to synthesize
- Claude autonomously decides whether to search or answer directly
- Sources tracked separately and returned to UI
- Session history maintained across queries
- All errors return gracefully (no crashes)

---

## Vector Search Details

This diagram shows the internal flow of semantic search in the vector store.

```
┌──────────────────────────────────────────────────────────────────┐
│ ENTRY POINT                                                      │
│ vector_store.search(query, course_name, lesson_number)          │
└──────────────────────────────────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ STEP 1:         │
                    │ Resolve Course  │
                    │ Name (Optional) │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ course_name     │
                    │ provided?       │
                    └────────┬────────┘
                        YES  │  NO
                    ┌────────┴────────┐
                    │                 │
                    ▼                 ▼
        ┌───────────────────┐    Skip to Step 2
        │ _resolve_course_  │
        │ name(course_name) │
        └────────┬──────────┘
                 │
                 ▼
        course_catalog.query(
            query_texts=[course_name],
            n_results=1
        )
                 │
                 ├─► EXAMPLE:
                 │   Input: "Computer Use" (partial/fuzzy)
                 │
                 │   ChromaDB embeds "Computer Use"
                 │   Compares with all course titles
                 │
                 │   Returns best match:
                 │   metadata[0]['title'] =
                 │   "Building Towards Computer Use with Anthropic"
                 │
                 ▼
        course_title = exact matched title
                 │
                 └─────────────┐
                               │
                    ┌──────────▼──────────┐
                    │ STEP 2:             │
                    │ Build Filter        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ _build_filter()     │
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
    Both provided         Course only          Lesson only
                               │
    {"$and": [           {"course_title":   {"lesson_number": N}
      {"course_title":     "exact title"}
       "exact title"},
      {"lesson_number":
       N}
    ]}
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ STEP 3:             │
                    │ Search Content      │
                    └──────────┬──────────┘
                               │
                               ▼
        course_content.query(
            query_texts=[query],
            n_results=5,
            where=filter_dict
        )
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼

    EMBEDDING              FILTERING           SIMILARITY RANKING
    (ChromaDB)             (ChromaDB)          (ChromaDB)
        │                      │                      │
        ▼                      ▼                      ▼

    SentenceTransformer    Apply where clause   Cosine similarity:
    encodes query:         on metadata:
                                                similarity =
    "prompt caching"       course_title ==        dot(v1, v2) /
    →                      "Building..."            (||v1|| * ||v2||)
    [0.12, -0.45,          AND/OR
     0.33, ..., 0.08]      lesson_number == 3   Higher = more similar
    (384 dimensions)
                           Only search in       Sort by similarity
                           filtered chunks      Return top N
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────┐
        │ CHROMADB RETURNS:                        │
        ├──────────────────────────────────────────┤
        │ documents: [                             │
        │   "Course XYZ Lesson 3 content: ...",    │
        │   "Course XYZ Lesson 2 content: ...",    │
        │   ...                                    │
        │ ]                                        │
        │                                          │
        │ metadatas: [                             │
        │   {course_title: "XYZ",                  │
        │    lesson_number: 3,                     │
        │    chunk_index: 15},                     │
        │   {course_title: "XYZ",                  │
        │    lesson_number: 2,                     │
        │    chunk_index: 8},                      │
        │   ...                                    │
        │ ]                                        │
        │                                          │
        │ distances: [0.12, 0.18, 0.22, ...]       │
        │ (lower = more similar)                   │
        └──────────────────┬───────────────────────┘
                           │
                           ▼
        SearchResults.from_chroma(chroma_results)
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │ SEARCHRESULTS OBJECT:                    │
        ├──────────────────────────────────────────┤
        │ documents: List[str]                     │
        │ metadata: List[Dict]                     │
        │ distances: List[float]                   │
        │ error: Optional[str] = None              │
        │                                          │
        │ Methods:                                 │
        │ - is_empty() → bool                      │
        │ - from_chroma(results) → SearchResults   │
        │ - empty(error_msg) → SearchResults       │
        └──────────────────┬───────────────────────┘
                           │
                           ▼
                    Return to caller
```

**Search Strategies:**

1. **No filters**: Searches entire `course_content` collection
2. **Course name only**:
   - First resolves fuzzy name → exact title via `course_catalog`
   - Then filters `course_content` by exact title
3. **Lesson number only**: Filters by `lesson_number` metadata
4. **Both**: Combines filters with `$and` operator

**Why Two Collections?**
- `course_catalog`: Small, optimized for fuzzy course name matching
- `course_content`: Large, contains all chunks with metadata for filtering

---

## Tool Execution Flow

This diagram shows how Claude's tool calling mechanism works in detail.

```
┌──────────────────────────────────────────────────────────────────┐
│ TOOL SYSTEM INITIALIZATION                                       │
│ (Happens once at RAG system startup)                            │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
        RAGSystem.__init__():
            tool_manager = ToolManager()
            search_tool = CourseSearchTool(vector_store)
            tool_manager.register_tool(search_tool)
                             │
                             ▼
        tool_manager.get_tool_definitions()
                             │
                             ▼
        ┌────────────────────────────────────────┐
        │ TOOL DEFINITION (Anthropic format)     │
        ├────────────────────────────────────────┤
        │ {                                      │
        │   "name": "search_course_content",     │
        │   "description": "Search course        │
        │                   materials with smart │
        │                   course name matching │
        │                   and lesson filtering",│
        │   "input_schema": {                    │
        │     "type": "object",                  │
        │     "properties": {                    │
        │       "query": {                       │
        │         "type": "string",              │
        │         "description": "What to search │
        │                         for in course  │
        │                         content"       │
        │       },                               │
        │       "course_name": {                 │
        │         "type": "string",              │
        │         "description": "Course title   │
        │                         (partial matches│
        │                         work)"         │
        │       },                               │
        │       "lesson_number": {               │
        │         "type": "integer",             │
        │         "description": "Specific lesson│
        │                         number"        │
        │       }                                │
        │     },                                 │
        │     "required": ["query"]              │
        │   }                                    │
        │ }                                      │
        └────────────────┬───────────────────────┘
                         │
                         │ This definition is sent to Claude
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ CLAUDE RECEIVES TOOL DEFINITION                                  │
└──────────────────────────────────────────────────────────────────┘
                             │
        Claude's internal reasoning:
        "I have access to search_course_content tool.
         I should use it when questions are about
         specific course content, lessons, or topics
         covered in the materials."
                             │
                             ▼
        User query arrives: "What is prompt caching?"
                             │
                             ▼
        Claude decides:
        "This is asking about course content
         → I should call search_course_content"
                             │
                             ▼
        ┌────────────────────────────────────────┐
        │ CLAUDE RETURNS tool_use                │
        ├────────────────────────────────────────┤
        │ stop_reason: "tool_use"                │
        │                                        │
        │ content: [{                            │
        │   "type": "tool_use",                  │
        │   "id": "toolu_01A2B3C4",              │
        │   "name": "search_course_content",     │
        │   "input": {                           │
        │     "query": "prompt caching",         │
        │     "course_name": null,               │
        │     "lesson_number": null              │
        │   }                                    │
        │ }]                                     │
        └────────────────┬───────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│ AI GENERATOR DETECTS TOOL USE                                    │
│ ai_generator.py:83-84                                           │
└──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
        if response.stop_reason == "tool_use":
            return _handle_tool_execution(...)
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ TOOL EXECUTION HANDLER                                           │
│ ai_generator.py:89-135                                          │
└──────────────────────────────────────────────────────────────────┘
                             │
        messages = base_params["messages"].copy()
        # [{"role": "user", "content": "What is prompt caching?"}]
                             │
                             ▼
        Add assistant's tool use to messages:
        messages.append({
            "role": "assistant",
            "content": response.content  # [tool_use block]
        })
                             │
                             ▼
        ┌────────────────────────────────────────┐
        │ EXECUTE EACH TOOL                      │
        └────────────────┬───────────────────────┘
                         │
                         ▼
        for content_block in response.content:
            if content_block.type == "tool_use":
                             │
                             ▼
                tool_result = tool_manager.execute_tool(
                    name=content_block.name,        # "search_course_content"
                    **content_block.input           # {query: "...", ...}
                )
                             │
                             ▼
        ┌────────────────────────────────────────────────────┐
        │ TOOL MANAGER                                       │
        │ search_tools.py:135-140                           │
        └────────────────┬───────────────────────────────────┘
                         │
                         ▼
        def execute_tool(tool_name: str, **kwargs):
            if tool_name not in self.tools:
                return "Tool not found"

            return self.tools[tool_name].execute(**kwargs)
                         │
                         ▼
        ┌────────────────────────────────────────────────────┐
        │ COURSE SEARCH TOOL                                 │
        │ search_tools.py:52-86                             │
        └────────────────┬───────────────────────────────────┘
                         │
                         ▼
        def execute(query, course_name=None, lesson_number=None):
            # Call vector store
            results = self.store.search(
                query=query,
                course_name=course_name,
                lesson_number=lesson_number
            )
                         │
                         ├─► Handle errors
                         │   if results.error: return error message
                         │
                         ├─► Handle empty
                         │   if results.is_empty(): return "No content found"
                         │
                         ▼
            # Format results
            return self._format_results(results)
                         │
                         ▼
        ┌────────────────────────────────────────────────────┐
        │ FORMAT RESULTS                                     │
        │ search_tools.py:88-114                            │
        └────────────────┬───────────────────────────────────┘
                         │
                         ▼
        formatted = []
        sources = []

        for doc, meta in zip(results.documents, results.metadata):
            course_title = meta['course_title']
            lesson_num = meta['lesson_number']

            # Build header
            header = f"[{course_title}"
            if lesson_num is not None:
                header += f" - Lesson {lesson_num}"
            header += "]"

            # Track source
            source = course_title
            if lesson_num is not None:
                source += f" - Lesson {lesson_num}"
            sources.append(source)

            # Format result
            formatted.append(f"{header}\n{doc}")

        # Store for later retrieval
        self.last_sources = sources

        return "\n\n".join(formatted)
                         │
                         ▼
        Returns to tool_manager → ai_generator
                         │
                         ▼
        ┌────────────────────────────────────────────────────┐
        │ COLLECT TOOL RESULTS                               │
        └────────────────┬───────────────────────────────────┘
                         │
                         ▼
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": content_block.id,  # "toolu_01A2B3C4"
            "content": tool_result             # Formatted search results
        })
                         │
                         ▼
        ┌────────────────────────────────────────────────────┐
        │ BUILD MESSAGE HISTORY FOR SECOND CALL              │
        └────────────────┬───────────────────────────────────┘
                         │
                         ▼
        messages.append({
            "role": "user",
            "content": tool_results  # List of tool_result objects
        })
                         │
        Now messages = [
            {"role": "user", "content": "What is prompt caching?"},
            {"role": "assistant", "content": [tool_use block]},
            {"role": "user", "content": [tool_result blocks]}
        ]
                         │
                         ▼
        ┌────────────────────────────────────────────────────┐
        │ SECOND CLAUDE API CALL                             │
        └────────────────┬───────────────────────────────────┘
                         │
                         ▼
        client.messages.create(
            messages=messages,
            system=system_prompt,
            # NOTE: No tools in second call
        )
                         │
                         ▼
        Claude sees the search results and synthesizes:

        "Prompt caching is a feature that retains
         some of the results of processing prompts
         between invocations to the model, which can
         be a large cost and latency saver..."
                         │
                         ▼
        Returns:
        stop_reason: "end_turn"
        content: [{"type": "text", "text": "[answer]"}]
                         │
                         ▼
        return final_response.content[0].text
```

**Tool Calling Key Points:**

1. **Two API calls**: First to decide tools, second to synthesize
2. **Autonomous decision**: Claude decides when to use tools based on query
3. **Extensible**: New tools can be added by implementing `Tool` interface
4. **Source tracking**: Search tool stores sources in `last_sources` for UI
5. **Error handling**: Tools return error messages as strings (no exceptions)
6. **Message format**: Specific structure required by Anthropic API

**Adding a New Tool:**

```python
class MyNewTool(Tool):
    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": "my_tool_name",
            "description": "What this tool does",
            "input_schema": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "..."},
                    # ...
                },
                "required": ["param1"]
            }
        }

    def execute(self, param1: str, **kwargs) -> str:
        # Tool logic here
        return "tool result as string"

# Register in RAGSystem.__init__:
self.tool_manager.register_tool(MyNewTool())
```

---

## Summary

These flow diagrams illustrate:

1. **Document Loading**: How course materials are parsed, chunked, and stored in ChromaDB
2. **User Query**: Complete request/response cycle from frontend to backend
3. **Vector Search**: Internal mechanics of semantic search with filtering
4. **Tool Execution**: How Claude's function calling works with custom tools

For code references, see file paths and line numbers noted throughout the diagrams.
