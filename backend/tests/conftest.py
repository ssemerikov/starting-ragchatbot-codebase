"""Shared pytest fixtures for testing the RAG system"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import Mock, MagicMock
from typing import List, Dict

from config import config
from rag_system import RAGSystem
from vector_store import VectorStore, SearchResults
from ai_generator import AIGenerator
from search_tools import ToolManager, CourseSearchTool
from session_manager import SessionManager


# ============================================================================
# RAG System Fixtures
# ============================================================================

@pytest.fixture
def rag_system():
    """Create a RAG system instance for testing"""
    return RAGSystem(config)


@pytest.fixture
def vector_store():
    """Create a vector store instance for testing"""
    return VectorStore(
        config.CHROMA_PATH,
        config.EMBEDDING_MODEL,
        config.MAX_RESULTS
    )


@pytest.fixture
def ai_generator():
    """Create an AI generator instance for testing"""
    return AIGenerator(
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
        model=config.DEFAULT_MODEL,
        fallback_models=config.FALLBACK_MODELS
    )


@pytest.fixture
def tool_manager(vector_store):
    """Create a tool manager with search tool registered"""
    manager = ToolManager()
    search_tool = CourseSearchTool(vector_store)
    manager.register_tool(search_tool)
    return manager


@pytest.fixture
def session_manager():
    """Create a session manager instance for testing"""
    return SessionManager(max_history=config.MAX_HISTORY)


# ============================================================================
# Mock Data Fixtures
# ============================================================================

@pytest.fixture
def sample_course_data():
    """Sample course data for testing"""
    return {
        "title": "Test Course on MCP",
        "instructor": "Test Instructor",
        "lessons": [
            {
                "number": 0,
                "title": "Introduction to MCP",
                "content": "MCP stands for Model Context Protocol. It is used for AI applications."
            },
            {
                "number": 1,
                "title": "Advanced MCP Concepts",
                "content": "Advanced features of MCP include tool calling and context management."
            }
        ]
    }


@pytest.fixture
def sample_search_results():
    """Sample search results for testing"""
    return SearchResults(
        documents=[
            "Course: Test Course on MCP, Lesson 0: MCP stands for Model Context Protocol.",
            "Course: Test Course on MCP, Lesson 1: Advanced features of MCP include tool calling."
        ],
        metadata=[
            {"course_title": "Test Course on MCP", "lesson_number": 0},
            {"course_title": "Test Course on MCP", "lesson_number": 1}
        ],
        distances=[0.2, 0.3],
        error=None
    )


@pytest.fixture
def sample_query_request():
    """Sample query request data for API testing"""
    return {
        "query": "What is MCP?",
        "session_id": None
    }


@pytest.fixture
def sample_query_response():
    """Sample query response data for API testing"""
    return {
        "answer": "MCP stands for Model Context Protocol, a system for AI applications.",
        "sources": [
            {"label": "Test Course on MCP - Lesson 0", "url": None}
        ],
        "session_id": "test-session-123"
    }


@pytest.fixture
def sample_course_stats():
    """Sample course statistics for testing"""
    return {
        "total_courses": 2,
        "course_titles": ["Test Course on MCP", "Another Test Course"]
    }


# ============================================================================
# Mock API Response Fixtures
# ============================================================================

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response without tool calls"""
    mock_choice = MagicMock()
    mock_choice.message.content = "MCP stands for Model Context Protocol."
    mock_choice.message.tool_calls = None
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    return mock_response


@pytest.fixture
def mock_openai_tool_call_response():
    """Mock OpenAI API response with tool calls"""
    # First response with tool call
    mock_tool_call = MagicMock()
    mock_tool_call.id = "call_123"
    mock_tool_call.function.name = "search_course_content"
    mock_tool_call.function.arguments = '{"query": "What is MCP?"}'

    mock_choice = MagicMock()
    mock_choice.message.tool_calls = [mock_tool_call]
    mock_choice.message.content = None
    mock_choice.finish_reason = "tool_calls"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    return mock_response


@pytest.fixture
def mock_openai_final_response():
    """Mock OpenAI API final response after tool execution"""
    mock_choice = MagicMock()
    mock_choice.message.content = "Based on the search results, MCP is a protocol for AI applications."
    mock_choice.message.tool_calls = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    return mock_response


# ============================================================================
# Mock Component Fixtures
# ============================================================================

@pytest.fixture
def mock_vector_store(sample_search_results):
    """Create a mock vector store that returns sample results"""
    mock_store = Mock(spec=VectorStore)
    mock_store.search.return_value = sample_search_results
    mock_store.get_course_count.return_value = 2
    mock_store.get_existing_course_titles.return_value = ["Test Course on MCP", "Another Test Course"]
    return mock_store


@pytest.fixture
def mock_ai_generator():
    """Create a mock AI generator"""
    mock_gen = Mock(spec=AIGenerator)
    mock_gen.generate_response.return_value = "MCP stands for Model Context Protocol."
    mock_gen.get_current_model.return_value = "claude-sonnet-4-20250514"
    mock_gen.set_model.return_value = None
    return mock_gen


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager"""
    mock_manager = Mock(spec=SessionManager)
    mock_manager.create_session.return_value = "test-session-123"
    mock_manager.add_interaction.return_value = None
    mock_manager.get_conversation_history.return_value = "Previous conversation history"
    return mock_manager


@pytest.fixture
def mock_rag_system(mock_vector_store, mock_ai_generator, mock_session_manager):
    """Create a mock RAG system with mocked components"""
    mock_rag = Mock(spec=RAGSystem)
    mock_rag.vector_store = mock_vector_store
    mock_rag.ai_generator = mock_ai_generator
    mock_rag.session_manager = mock_session_manager
    mock_rag.query.return_value = (
        "MCP stands for Model Context Protocol.",
        [{"label": "Test Course on MCP - Lesson 0", "url": None}]
    )
    mock_rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Test Course on MCP", "Another Test Course"]
    }
    return mock_rag


# ============================================================================
# Test Environment Setup
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def suppress_warnings():
    """Suppress resource tracker warnings during tests"""
    import warnings
    warnings.filterwarnings("ignore", message="resource_tracker: There appear to be.*")


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config to default values before each test"""
    # This ensures tests don't interfere with each other
    yield
    # Add any cleanup needed after tests
