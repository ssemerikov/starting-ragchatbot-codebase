"""Tests for RAG System integration"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from config import config
from rag_system import RAGSystem


class TestRAGSystemQueries:
    """Test RAG system's handling of content queries"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.rag_system = RAGSystem(config)

    def test_rag_system_initialization(self):
        """Test that RAG system initializes correctly"""
        print("\n=== Test RAG System Initialization ===")

        assert self.rag_system.vector_store is not None
        assert self.rag_system.ai_generator is not None
        assert self.rag_system.tool_manager is not None
        assert self.rag_system.session_manager is not None

        print(f"Vector store: {type(self.rag_system.vector_store)}")
        print(f"AI generator: {type(self.rag_system.ai_generator)}")
        print(f"Tool manager: {type(self.rag_system.tool_manager)}")
        print(f"Session manager: {type(self.rag_system.session_manager)}")

    def test_tool_registration(self):
        """Test that tools are registered in the tool manager"""
        print("\n=== Test Tool Registration ===")

        tools = self.rag_system.tool_manager.get_tool_definitions()

        print(f"Number of registered tools: {len(tools)}")
        for i, tool in enumerate(tools):
            print(f"\nTool {i+1}:")
            print(f"  Name: {tool.get('function', {}).get('name')}")
            print(f"  Description: {tool.get('function', {}).get('description')}")

        assert len(tools) >= 1  # Should have at least search_course_content
        tool_names = [t.get("function", {}).get("name") for t in tools]
        assert "search_course_content" in tool_names

    def test_course_analytics(self):
        """Test course analytics endpoint"""
        print("\n=== Test Course Analytics ===")

        analytics = self.rag_system.get_course_analytics()

        print(f"Total courses: {analytics['total_courses']}")
        print(f"Course titles: {analytics['course_titles']}")

        assert "total_courses" in analytics
        assert "course_titles" in analytics
        assert analytics["total_courses"] > 0
        assert len(analytics["course_titles"]) > 0

    @pytest.mark.skipif(not config.OPENROUTER_API_KEY, reason="No API key")
    def test_simple_content_query(self):
        """Test a simple content query through the RAG system"""
        print("\n=== Test Simple Content Query ===")

        query = "What is MCP?"
        print(f"Query: {query}")

        try:
            response, sources = self.rag_system.query(query)

            print(f"\nResponse type: {type(response)}")
            print(f"Response length: {len(response)}")
            print(f"Response: {response}")
            print(f"\nSources: {sources}")

            assert isinstance(response, str)
            assert len(response) > 0
            assert not response.startswith("Error")

        except Exception as e:
            print(f"\nException occurred: {type(e).__name__}")
            print(f"Exception message: {str(e)}")
            import traceback

            print(f"Traceback:\n{traceback.format_exc()}")
            raise

    @pytest.mark.skipif(not config.OPENROUTER_API_KEY, reason="No API key")
    def test_query_with_session(self):
        """Test query with session management"""
        print("\n=== Test Query with Session ===")

        session_id = self.rag_system.session_manager.create_session()
        print(f"Created session: {session_id}")

        query = "What is covered in the MCP course?"
        print(f"Query: {query}")

        try:
            response, sources = self.rag_system.query(query, session_id)

            print(f"\nResponse: {response}")
            print(f"Sources: {sources}")

            assert isinstance(response, str)
            assert len(response) > 0

            # Check session history
            history = self.rag_system.session_manager.get_conversation_history(
                session_id
            )
            print(f"\nSession history:\n{history}")

            assert history is not None

        except Exception as e:
            print(f"\nException occurred: {type(e).__name__}")
            print(f"Exception message: {str(e)}")
            import traceback

            print(f"Traceback:\n{traceback.format_exc()}")
            raise

    def test_tool_manager_has_both_tools(self):
        """Test that both search and outline tools are registered"""
        print("\n=== Test Both Tools Registered ===")

        tools = self.rag_system.tool_manager.get_tool_definitions()
        tool_names = [t.get("function", {}).get("name") for t in tools]

        print(f"Registered tools: {tool_names}")

        assert "search_course_content" in tool_names
        assert "get_course_outline" in tool_names


class TestVectorStoreIntegration:
    """Test vector store functionality"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.rag_system = RAGSystem(config)
        self.vector_store = self.rag_system.vector_store

    def test_vector_store_has_courses(self):
        """Test that vector store has courses loaded"""
        print("\n=== Test Vector Store Has Courses ===")

        course_count = self.vector_store.get_course_count()
        course_titles = self.vector_store.get_existing_course_titles()

        print(f"Course count: {course_count}")
        print(f"Course titles: {course_titles}")

        assert course_count > 0
        assert len(course_titles) > 0

    def test_vector_store_search_directly(self):
        """Test vector store search functionality directly"""
        print("\n=== Test Vector Store Search Directly ===")

        query = "What is MCP?"
        print(f"Query: {query}")

        results = self.vector_store.search(query)

        print(f"\nResults type: {type(results)}")
        print(f"Results error: {results.error}")
        print(f"Results documents count: {len(results.documents)}")
        print(f"Results is_empty: {results.is_empty()}")

        if not results.is_empty():
            print(f"\nFirst document preview: {results.documents[0][:200]}")
            print(f"First metadata: {results.metadata[0]}")

        assert results.error is None or results.error == ""
        assert not results.is_empty()

    def test_vector_store_search_with_filter(self):
        """Test vector store search with course filter"""
        print("\n=== Test Vector Store Search with Filter ===")

        query = "lesson content"
        course_name = "MCP"
        print(f"Query: {query}")
        print(f"Course filter: {course_name}")

        results = self.vector_store.search(query, course_name=course_name)

        print(f"\nResults error: {results.error}")
        print(f"Results documents count: {len(results.documents)}")

        if results.error:
            print(f"Error message: {results.error}")

        # Results might be empty, but there shouldn't be an error
        assert results.error is None or "No course found" in results.error


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
