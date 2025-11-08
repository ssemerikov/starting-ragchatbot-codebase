"""Tests for AI Generator tool calling functionality"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import Mock, MagicMock, patch
from ai_generator import AIGenerator
from search_tools import ToolManager, CourseSearchTool
from vector_store import VectorStore
from config import config


class TestAIGeneratorToolCalling:
    """Test AI Generator's ability to call tools correctly"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        # Create AI generator with real config
        self.ai_generator = AIGenerator(
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            model=config.DEFAULT_MODEL,
            fallback_models=config.FALLBACK_MODELS
        )

        # Create real tool manager and search tool
        self.vector_store = VectorStore(
            config.CHROMA_PATH,
            config.EMBEDDING_MODEL,
            config.MAX_RESULTS
        )
        self.tool_manager = ToolManager()
        self.search_tool = CourseSearchTool(self.vector_store)
        self.tool_manager.register_tool(self.search_tool)

    def test_tool_definitions_format(self):
        """Test that tools are properly formatted for OpenAI API"""
        print("\n=== Test Tool Definitions Format ===")

        tool_defs = self.tool_manager.get_tool_definitions()

        print(f"Number of tools: {len(tool_defs)}")
        for i, tool_def in enumerate(tool_defs):
            print(f"\nTool {i+1}:")
            print(f"  Type: {tool_def.get('type')}")
            print(f"  Function name: {tool_def.get('function', {}).get('name')}")
            print(f"  Description: {tool_def.get('function', {}).get('description')}")
            print(f"  Parameters: {tool_def.get('function', {}).get('parameters')}")

        assert len(tool_defs) > 0
        assert all(tool.get("type") == "function" for tool in tool_defs)
        assert all("function" in tool for tool in tool_defs)
        assert all("name" in tool.get("function", {}) for tool in tool_defs)

    def test_tool_manager_execution(self):
        """Test that tool manager can execute tools"""
        print("\n=== Test Tool Manager Execution ===")

        query = "What is MCP?"
        print(f"Testing tool execution with query: {query}")

        result = self.tool_manager.execute_tool(
            "search_course_content",
            query=query
        )

        print(f"Result type: {type(result)}")
        print(f"Result length: {len(result)}")
        print(f"Result preview (first 500 chars): {result[:500]}")

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.skipif(not config.OPENROUTER_API_KEY, reason="No API key")
    def test_ai_generator_with_tools_real_api(self):
        """Test AI generator with real API call (requires API key)"""
        print("\n=== Test AI Generator with Real API ===")

        query = "What is MCP? Search the course content to answer this."
        print(f"Query: {query}")

        tool_defs = self.tool_manager.get_tool_definitions()
        print(f"Providing {len(tool_defs)} tools to AI")

        try:
            response = self.ai_generator.generate_response(
                query=query,
                tools=tool_defs,
                tool_manager=self.tool_manager
            )

            print(f"\nResponse type: {type(response)}")
            print(f"Response length: {len(response)}")
            print(f"Response: {response}")

            assert isinstance(response, str)
            assert len(response) > 0
            assert "Error" not in response[:50]  # Check if starts with error

        except Exception as e:
            print(f"\nException occurred: {type(e).__name__}")
            print(f"Exception message: {str(e)}")
            raise

    def test_system_prompt_contains_tool_info(self):
        """Test that system prompt includes tool information"""
        print("\n=== Test System Prompt ===")

        system_prompt = self.ai_generator.SYSTEM_PROMPT

        print(f"System prompt length: {len(system_prompt)}")
        print(f"\nSystem prompt preview (first 800 chars):\n{system_prompt[:800]}")

        assert "search_course_content" in system_prompt.lower()
        assert "tool" in system_prompt.lower()


class TestToolCallFlow:
    """Test the complete flow of tool calling"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.vector_store = VectorStore(
            config.CHROMA_PATH,
            config.EMBEDDING_MODEL,
            config.MAX_RESULTS
        )
        self.tool_manager = ToolManager()
        self.search_tool = CourseSearchTool(self.vector_store)
        self.tool_manager.register_tool(self.search_tool)

    def test_mock_tool_call_flow(self):
        """Test tool call flow with mocked API responses"""
        print("\n=== Test Mock Tool Call Flow ===")

        # Create a mock response that simulates tool calling
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "search_course_content"
        mock_tool_call.function.arguments = '{"query": "What is MCP?"}'

        mock_choice = MagicMock()
        mock_choice.finish_reason = "tool_calls"
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_choice.message.content = None

        mock_initial_response = MagicMock()
        mock_initial_response.choices = [mock_choice]

        # Create final response
        mock_final_choice = MagicMock()
        mock_final_choice.message.content = "MCP is a protocol for AI applications."

        mock_final_response = MagicMock()
        mock_final_response.choices = [mock_final_choice]

        # Test that tool gets executed
        with patch.object(AIGenerator, '__init__', return_value=None):
            ai_gen = AIGenerator.__new__(AIGenerator)
            ai_gen.client = MagicMock()
            ai_gen.base_params = {"temperature": 0, "max_tokens": 800}
            ai_gen.fallback_models = []

            # Mock the API calls
            ai_gen.client.chat.completions.create.side_effect = [
                mock_initial_response,
                mock_final_response
            ]

            # Test _handle_tool_execution
            messages = [
                {"role": "system", "content": "test"},
                {"role": "user", "content": "What is MCP?"}
            ]
            base_params = {"model": "test-model"}

            result = ai_gen._handle_tool_execution(
                mock_initial_response,
                messages,
                base_params,
                self.tool_manager
            )

            print(f"Result: {result}")
            assert result == "MCP is a protocol for AI applications."


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
