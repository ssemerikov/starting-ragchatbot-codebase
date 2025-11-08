"""Tests for CourseSearchTool functionality"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from config import config
from search_tools import CourseSearchTool
from vector_store import VectorStore


class TestCourseSearchTool:
    """Test CourseSearchTool.execute() method"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        # Use existing vector store with loaded courses
        self.vector_store = VectorStore(
            config.CHROMA_PATH, config.EMBEDDING_MODEL, config.MAX_RESULTS
        )
        self.search_tool = CourseSearchTool(self.vector_store)

    def test_tool_definition(self):
        """Test that tool definition is properly formatted"""
        tool_def = self.search_tool.get_tool_definition()

        print("\n=== Tool Definition ===")
        print(f"Type: {tool_def.get('type')}")
        print(f"Function name: {tool_def.get('function', {}).get('name')}")
        print(f"Description: {tool_def.get('function', {}).get('description')}")
        print(f"Parameters: {tool_def.get('function', {}).get('parameters')}")

        assert tool_def["type"] == "function"
        assert tool_def["function"]["name"] == "search_course_content"
        assert "query" in tool_def["function"]["parameters"]["properties"]
        assert "query" in tool_def["function"]["parameters"]["required"]

    def test_simple_search(self):
        """Test basic search without filters"""
        print("\n=== Test Simple Search ===")
        query = "What is MCP?"
        print(f"Query: {query}")

        result = self.search_tool.execute(query=query)

        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)}")
        print(f"Result preview (first 500 chars): {result[:500]}")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "No relevant content found" not in result or "MCP" in result

    def test_search_with_course_filter(self):
        """Test search with course name filter"""
        print("\n=== Test Search with Course Filter ===")
        query = "What is covered in this course?"
        course_name = "MCP"
        print(f"Query: {query}")
        print(f"Course filter: {course_name}")

        result = self.search_tool.execute(query=query, course_name=course_name)

        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)}")
        print(f"Result preview (first 500 chars): {result[:500]}")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_search_with_lesson_filter(self):
        """Test search with lesson number filter"""
        print("\n=== Test Search with Lesson Filter ===")
        query = "lesson content"
        course_name = "MCP"
        lesson_number = 0
        print(f"Query: {query}")
        print(f"Course filter: {course_name}")
        print(f"Lesson filter: {lesson_number}")

        result = self.search_tool.execute(
            query=query, course_name=course_name, lesson_number=lesson_number
        )

        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)}")
        print(f"Result preview (first 500 chars): {result[:500]}")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_search_no_results(self):
        """Test search that should return no results"""
        print("\n=== Test Search No Results ===")
        query = "xyzabc123impossible-to-find-term"
        print(f"Query: {query}")

        result = self.search_tool.execute(query=query)

        print(f"Result: {result}")

        assert isinstance(result, str)
        assert "No relevant content found" in result or len(result) > 0

    def test_source_tracking(self):
        """Test that sources are tracked correctly"""
        print("\n=== Test Source Tracking ===")
        query = "MCP introduction"
        print(f"Query: {query}")

        # Clear any previous sources
        self.search_tool.last_sources = []

        result = self.search_tool.execute(query=query)

        print(f"Result length: {len(result)}")
        print(f"Number of sources: {len(self.search_tool.last_sources)}")
        print(f"Sources: {self.search_tool.last_sources}")

        assert isinstance(self.search_tool.last_sources, list)
        # Sources should be populated if results were found
        if "No relevant content found" not in result:
            assert len(self.search_tool.last_sources) > 0
            # Check source structure
            if len(self.search_tool.last_sources) > 0:
                source = self.search_tool.last_sources[0]
                assert "label" in source
                assert "url" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
