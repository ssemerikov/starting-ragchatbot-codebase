"""Tests for sequential tool calling functionality"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import MagicMock, Mock, patch

import pytest
from ai_generator import AIGenerator
from config import config
from search_tools import CourseSearchTool, ToolManager
from vector_store import VectorStore


class TestSequentialToolCalling:
    """Test sequential tool calling with iterative approach"""

    @pytest.fixture
    def mock_tool_manager(self):
        """Create mock tool manager"""
        manager = Mock()
        manager.execute_tool = Mock(return_value="Tool result")
        manager.get_tool_definitions = Mock(
            return_value=[
                {
                    "type": "function",
                    "function": {
                        "name": "search_course_content",
                        "description": "Search course content",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    },
                }
            ]
        )
        return manager

    def _create_tool_call_response(self, tool_name: str, tool_args: str, tool_id: str):
        """Helper: Create mock response with tool calls"""
        response = Mock()
        response.choices = [Mock()]

        tool_call = Mock()
        tool_call.id = tool_id
        tool_call.type = "function"
        tool_call.function = Mock()
        tool_call.function.name = tool_name
        tool_call.function.arguments = tool_args

        response.choices[0].message = Mock()
        response.choices[0].message.tool_calls = [tool_call]
        response.choices[0].message.content = None
        response.choices[0].finish_reason = "tool_calls"

        return response

    def _create_text_response(self, content: str):
        """Helper: Create mock response with text content"""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = content
        response.choices[0].message.tool_calls = None
        response.choices[0].finish_reason = "stop"

        return response

    def test_single_tool_call_round(self, mock_tool_manager):
        """Test that single tool call still works (baseline behavior)"""
        print("\n=== Test Single Tool Call ===")

        with patch("ai_generator.OpenAI"):
            ai_gen = AIGenerator(
                api_key="test",
                base_url="https://test.url",
                model="test-model",
                fallback_models=[],
            )
            ai_gen.client = Mock()

            # Mock responses: tool call → final answer
            initial_response = self._create_tool_call_response(
                "search_course_content", '{"query": "MCP"}', "call_1"
            )
            final_response = self._create_text_response("Here's what MCP covers...")

            ai_gen.client.chat.completions.create = Mock(
                side_effect=[initial_response, final_response]
            )

            # Execute
            result = ai_gen.generate_response(
                query="What does MCP cover?",
                tools=[
                    {"type": "function", "function": {"name": "search_course_content"}}
                ],
                tool_manager=mock_tool_manager,
            )

            print(f"Result: {result}")
            print(f"API calls: {ai_gen.client.chat.completions.create.call_count}")
            print(f"Tool executions: {mock_tool_manager.execute_tool.call_count}")

            # Verify
            assert "MCP covers" in result
            assert (
                ai_gen.client.chat.completions.create.call_count == 2
            )  # Initial + after tools
            assert mock_tool_manager.execute_tool.call_count == 1

    def test_two_sequential_tool_calls(self, mock_tool_manager):
        """Test two sequential tool calls (main new feature)"""
        print("\n=== Test Two Sequential Tool Calls ===")

        # Setup tool results
        mock_tool_manager.execute_tool = Mock(
            side_effect=["MCP result", "Chroma result"]
        )

        with patch("ai_generator.OpenAI"):
            ai_gen = AIGenerator(
                api_key="test",
                base_url="https://test.url",
                model="test-model",
                fallback_models=[],
            )
            ai_gen.client = Mock()

            # Mock responses: Round 1 tool → Round 2 tool → Final answer
            round1_response = self._create_tool_call_response(
                "search_course_content",
                '{"query": "MCP", "lesson_number": 4}',
                "call_1",
            )
            round2_response = self._create_tool_call_response(
                "search_course_content",
                '{"query": "Chroma", "lesson_number": 2}',
                "call_2",
            )
            final_response = self._create_text_response(
                "Comparing MCP vs Chroma: MCP focuses on X while Chroma covers Y."
            )

            ai_gen.client.chat.completions.create = Mock(
                side_effect=[round1_response, round2_response, final_response]
            )

            # Execute
            result = ai_gen.generate_response(
                query="Compare MCP lesson 4 vs Chroma lesson 2",
                tools=[
                    {"type": "function", "function": {"name": "search_course_content"}}
                ],
                tool_manager=mock_tool_manager,
            )

            print(f"Result: {result}")
            print(f"API calls: {ai_gen.client.chat.completions.create.call_count}")
            print(f"Tool executions: {mock_tool_manager.execute_tool.call_count}")

            # Verify
            assert "Comparing" in result or "MCP" in result
            assert (
                ai_gen.client.chat.completions.create.call_count == 3
            )  # Round1 + Round2 + Final
            assert mock_tool_manager.execute_tool.call_count == 2  # Two tool calls

    def test_early_termination_no_tools(self, mock_tool_manager):
        """Test early termination when Claude doesn't use tools in first response"""
        print("\n=== Test Early Termination (No Tools) ===")

        with patch("ai_generator.OpenAI"):
            ai_gen = AIGenerator(
                api_key="test",
                base_url="https://test.url",
                model="test-model",
                fallback_models=[],
            )
            ai_gen.client = Mock()

            # Claude responds directly without tools
            direct_response = self._create_text_response(
                "This is general knowledge, no search needed."
            )

            ai_gen.client.chat.completions.create = Mock(return_value=direct_response)

            result = ai_gen.generate_response(
                query="What is machine learning?",
                tools=[
                    {"type": "function", "function": {"name": "search_course_content"}}
                ],
                tool_manager=mock_tool_manager,
            )

            print(f"Result: {result}")
            print(f"API calls: {ai_gen.client.chat.completions.create.call_count}")
            print(f"Tool executions: {mock_tool_manager.execute_tool.call_count}")

            # Verify
            assert "general knowledge" in result
            assert (
                ai_gen.client.chat.completions.create.call_count == 1
            )  # Only initial call
            assert mock_tool_manager.execute_tool.call_count == 0  # No tools used

    def test_early_termination_after_one_round(self, mock_tool_manager):
        """Test early termination when Claude uses tool once then answers"""
        print("\n=== Test Early Termination (After One Round) ===")

        with patch("ai_generator.OpenAI"):
            ai_gen = AIGenerator(
                api_key="test",
                base_url="https://test.url",
                model="test-model",
                fallback_models=[],
            )
            ai_gen.client = Mock()

            # Round 1: tool call → Round 2: direct answer (no tools)
            round1_response = self._create_tool_call_response(
                "search_course_content", '{"query": "MCP"}', "call_1"
            )
            final_response = self._create_text_response(
                "Based on the search, here's the answer..."
            )

            ai_gen.client.chat.completions.create = Mock(
                side_effect=[round1_response, final_response]
            )

            result = ai_gen.generate_response(
                query="Tell me about MCP",
                tools=[
                    {"type": "function", "function": {"name": "search_course_content"}}
                ],
                tool_manager=mock_tool_manager,
            )

            print(f"Result: {result}")
            print(f"API calls: {ai_gen.client.chat.completions.create.call_count}")
            print(f"Tool executions: {mock_tool_manager.execute_tool.call_count}")

            # Verify
            assert "answer" in result
            assert (
                ai_gen.client.chat.completions.create.call_count == 2
            )  # Round1 + Final
            assert mock_tool_manager.execute_tool.call_count == 1  # Only one tool call

    def test_max_rounds_enforcement(self, mock_tool_manager):
        """Test that system enforces 2-round maximum"""
        print("\n=== Test Max Rounds Enforcement ===")

        with patch("ai_generator.OpenAI"):
            ai_gen = AIGenerator(
                api_key="test",
                base_url="https://test.url",
                model="test-model",
                fallback_models=[],
            )
            ai_gen.client = Mock()

            # Claude keeps trying to call tools (3 responses with tool calls)
            tool_response_1 = self._create_tool_call_response(
                "search", '{"q":"1"}', "call_1"
            )
            tool_response_2 = self._create_tool_call_response(
                "search", '{"q":"2"}', "call_2"
            )
            # After round 2, tools are removed, so this would be final response
            final_response = self._create_text_response("Final answer after 2 rounds")

            ai_gen.client.chat.completions.create = Mock(
                side_effect=[tool_response_1, tool_response_2, final_response]
            )

            result = ai_gen.generate_response(
                query="Complex multi-step query",
                tools=[{"type": "function", "function": {"name": "search"}}],
                tool_manager=mock_tool_manager,
            )

            print(f"Result: {result}")
            print(f"API calls: {ai_gen.client.chat.completions.create.call_count}")
            print(f"Tool executions: {mock_tool_manager.execute_tool.call_count}")

            # Verify max 2 tool rounds executed
            assert (
                ai_gen.client.chat.completions.create.call_count == 3
            )  # Max: Round1 + Round2 + Final
            assert (
                mock_tool_manager.execute_tool.call_count == 2
            )  # Only 2 tool executions

    def test_message_accumulation_across_rounds(self, mock_tool_manager):
        """Test that messages accumulate correctly across rounds"""
        print("\n=== Test Message Accumulation ===")

        mock_tool_manager.execute_tool = Mock(side_effect=["Result 1", "Result 2"])

        with patch("ai_generator.OpenAI"):
            ai_gen = AIGenerator(
                api_key="test",
                base_url="https://test.url",
                model="test-model",
                fallback_models=[],
            )
            ai_gen.client = Mock()

            round1_response = self._create_tool_call_response(
                "search", '{"q":"1"}', "call_1"
            )
            round2_response = self._create_tool_call_response(
                "search", '{"q":"2"}', "call_2"
            )
            final_response = self._create_text_response("Final answer")

            ai_gen.client.chat.completions.create = Mock(
                side_effect=[round1_response, round2_response, final_response]
            )

            result = ai_gen.generate_response(
                query="Test query",
                tools=[{"type": "function", "function": {"name": "search"}}],
                tool_manager=mock_tool_manager,
            )

            # Verify message structure in API calls
            calls = ai_gen.client.chat.completions.create.call_args_list

            # Round 1: [system, user]
            round1_messages = calls[0][1]["messages"]
            print(f"\nRound 1 messages count: {len(round1_messages)}")
            assert len(round1_messages) == 2
            assert round1_messages[0]["role"] == "system"
            assert round1_messages[1]["role"] == "user"

            # Round 2: [system, user, assistant, tool]
            round2_messages = calls[1][1]["messages"]
            print(f"Round 2 messages count: {len(round2_messages)}")
            assert len(round2_messages) == 4
            assert round2_messages[2]["role"] == "assistant"
            assert round2_messages[3]["role"] == "tool"

            # Final: [system, user, assistant, tool, assistant, tool]
            final_messages = calls[2][1]["messages"]
            print(f"Final messages count: {len(final_messages)}")
            assert len(final_messages) == 6
            assert final_messages[4]["role"] == "assistant"
            assert final_messages[5]["role"] == "tool"

    def test_tools_availability_per_round(self, mock_tool_manager):
        """Test that tools are available in early rounds but removed in final call"""
        print("\n=== Test Tools Availability Per Round ===")

        with patch("ai_generator.OpenAI"):
            ai_gen = AIGenerator(
                api_key="test",
                base_url="https://test.url",
                model="test-model",
                fallback_models=[],
            )
            ai_gen.client = Mock()

            round1_response = self._create_tool_call_response(
                "search", '{"q":"1"}', "call_1"
            )
            round2_response = self._create_tool_call_response(
                "search", '{"q":"2"}', "call_2"
            )
            final_response = self._create_text_response("Final")

            ai_gen.client.chat.completions.create = Mock(
                side_effect=[round1_response, round2_response, final_response]
            )

            result = ai_gen.generate_response(
                query="Test",
                tools=[{"type": "function", "function": {"name": "search"}}],
                tool_manager=mock_tool_manager,
            )

            calls = ai_gen.client.chat.completions.create.call_args_list

            # Round 1: tools present
            print(f"\nRound 1 has tools: {'tools' in calls[0][1]}")
            assert "tools" in calls[0][1]

            # Round 2: tools present (still within max rounds)
            print(f"Round 2 has tools: {'tools' in calls[1][1]}")
            assert "tools" in calls[1][1]

            # Final call: no tools (exceeded max rounds)
            print(f"Final call has tools: {'tools' in calls[2][1]}")
            assert "tools" not in calls[2][1] or calls[2][1].get("tools") is None

    def test_api_error_handling(self, mock_tool_manager):
        """Test error handling during sequential tool calling"""
        print("\n=== Test API Error Handling ===")

        with patch("ai_generator.OpenAI"):
            ai_gen = AIGenerator(
                api_key="test",
                base_url="https://test.url",
                model="test-model",
                fallback_models=[],
            )
            ai_gen.client = Mock()

            round1_response = self._create_tool_call_response(
                "search", '{"q":"1"}', "call_1"
            )

            # Round 2 fails
            ai_gen.client.chat.completions.create = Mock(
                side_effect=[round1_response, Exception("Connection error")]
            )

            result = ai_gen.generate_response(
                query="Test query",
                tools=[{"type": "function", "function": {"name": "search"}}],
                tool_manager=mock_tool_manager,
            )

            print(f"Result: {result}")

            # Should get user-friendly error message
            assert result is not None
            assert len(result) > 0
            assert "unable to connect" in result.lower() or "error" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
