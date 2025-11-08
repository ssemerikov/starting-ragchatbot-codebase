import json
from typing import Any, Dict, List, Optional

from anthropic import Anthropic


class AIGenerator:
    """Handles interactions with Anthropic API for Claude"""

    # Maximum sequential tool calling rounds
    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to comprehensive tools for course information.

Available Tools:
1. **search_course_content**: Search for specific content within course materials, lessons, and detailed educational content
2. **get_course_outline**: Retrieve complete course outline including course title, instructor, course link, and all lessons with their titles and links

Tool Usage Guidelines:
- Use **get_course_outline** for questions about:
  - Course structure, outline, or table of contents
  - What lessons are in a course
  - Course metadata (instructor, links)
  - General course overview
- Use **search_course_content** for questions about:
  - Specific topics or concepts within course materials
  - Detailed lesson content
  - Technical information covered in courses

**Sequential Tool Calling:**
- You can make **up to 2 sequential tool calls** per query
- After seeing results from the first tool call, you may call another tool if needed
- Common patterns requiring multiple calls:
  - **Comparisons**: "Compare lesson X of course A vs lesson Y of course B"
    → First call: search course A/lesson X, Second call: search course B/lesson Y
  - **Multi-topic queries**: "What do courses teach about topic X and topic Y?"
    → First call: search for topic X, Second call: search for topic Y
  - **Overview then detail**: Get course outline first, then search specific lesson content
  - **Multiple courses**: Search different courses sequentially to gather comprehensive information
- Use multiple calls when:
  - Comparing content from different sources (courses, lessons)
  - User asks about multiple distinct topics or courses
  - Initial results suggest additional information is needed
- Synthesize all tool results into a cohesive final answer

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course outline/structure questions**: Use get_course_outline tool
- **Course content questions**: Use search_course_content tool (can use twice if needed for comparisons)
- **No meta-commentary**:
  - Provide direct answers only — no reasoning process, tool usage explanations, or question-type analysis
  - Do not mention "based on the search results" or "I called the tool twice"
  - Do not explain your multi-step process or number of searches performed

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
5. **Synthesized** - When using multiple tool calls, combine information seamlessly
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        """
        Initialize Anthropic client.

        Args:
            api_key: Anthropic API key
            model: Model to use (e.g., claude-sonnet-4-20250514)
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use (Anthropic format)
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """
        # Build system prompt with history if available
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Build initial messages (just user message, system is separate)
        messages = [{"role": "user", "content": query}]

        # Prepare API call parameters
        api_params = {
            **self.base_params,
            "model": self.model,
            "system": system_content,
            "messages": messages.copy(),
        }

        # Add tools if available (Anthropic format)
        if tools:
            api_params["tools"] = tools

        try:
            response = self.client.messages.create(**api_params)

            # Handle tool execution if needed
            if response.stop_reason == "tool_use" and tool_manager:
                return self._handle_tool_execution(
                    response, messages, api_params, tool_manager, system_content
                )

            # Return direct response
            return self._extract_text_content(response)

        except Exception as e:
            error_msg = str(e)
            # Provide user-friendly error messages
            if "Connection error" in error_msg or "connect" in error_msg.lower():
                return "I'm unable to connect to the AI service. Please check your network connection or try again later."
            elif "CERTIFICATE" in error_msg.upper() or "SSL" in error_msg.upper():
                return "I'm experiencing SSL/certificate issues connecting to the AI service. Please contact support."
            elif "timeout" in error_msg.lower():
                return "The AI service request timed out. Please try again."
            else:
                return f"I'm experiencing technical difficulties. Error: {error_msg[:100]}"

    def _extract_text_content(self, response) -> str:
        """Extract text content from Anthropic response"""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def _handle_tool_execution(
        self,
        initial_response,
        messages: List[Dict],
        base_params: Dict[str, Any],
        tool_manager,
        system_content: str,
    ) -> str:
        """
        Handle execution of tools with support for sequential rounds.
        Allows Claude to make multiple tool calls across up to MAX_TOOL_ROUNDS rounds.

        Args:
            initial_response: First response containing tool calls
            messages: Current message history [user]
            base_params: Base API parameters
            tool_manager: Manager to execute tools
            system_content: System prompt text

        Returns:
            Final response text after all rounds
        """
        current_round = 0
        current_response = initial_response

        # Main iteration loop
        while current_round < self.MAX_TOOL_ROUNDS:
            current_round += 1

            # Check if this response has tool calls
            has_tool_use = any(
                block.type == "tool_use" for block in current_response.content
            )

            if not has_tool_use:
                # Natural termination - Claude chose not to use tools
                return self._extract_text_content(current_response)

            # Process this round of tool calls
            messages = self._process_tool_round(
                current_response, messages, tool_manager
            )

            # Determine if tools should be available for next round
            should_include_tools = current_round < self.MAX_TOOL_ROUNDS

            # Build parameters for next API call
            next_params = {
                **self.base_params,
                "model": self.model,
                "system": system_content,
                "messages": messages.copy(),
            }

            # Add tools if we haven't reached max rounds
            if should_include_tools and "tools" in base_params:
                next_params["tools"] = base_params["tools"]

            # Make next API call
            try:
                current_response = self.client.messages.create(**next_params)
            except Exception as e:
                # Error handling - return partial results if available
                return self._handle_api_error(e, messages, current_round)

        # Max rounds reached - return final response
        return self._extract_text_content(current_response)

    def _process_tool_round(
        self, response, messages: List[Dict], tool_manager
    ) -> List[Dict]:
        """
        Process a single round of tool calling and accumulate results.

        Args:
            response: API response with tool calls
            messages: Current message list
            tool_manager: Tool execution manager

        Returns:
            Updated messages list with assistant message and tool results
        """
        # Add assistant's message with tool uses
        assistant_content = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
                tool_uses.append(block)

        messages.append({"role": "assistant", "content": assistant_content})

        # Execute each tool and collect results
        tool_results = []
        for tool_use in tool_uses:
            try:
                tool_result = tool_manager.execute_tool(tool_use.name, **tool_use.input)
            except Exception as e:
                tool_result = f"Error executing tool: {str(e)}"

            tool_results.append(
                {"type": "tool_result", "tool_use_id": tool_use.id, "content": tool_result}
            )

        # Add tool results as user message
        messages.append({"role": "user", "content": tool_results})

        return messages

    def _handle_api_error(
        self, error: Exception, messages: List[Dict], round_num: int
    ) -> str:
        """
        Handle API failures mid-flow with user-friendly messages.

        Args:
            error: The exception that occurred
            messages: Current message history
            round_num: Current round number

        Returns:
            User-friendly error message
        """
        error_msg = str(error)

        # Provide context-aware error messages
        if "Connection error" in error_msg or "connect" in error_msg.lower():
            return "I'm unable to connect to the AI service. Please check your network connection or try again later."
        elif "CERTIFICATE" in error_msg.upper() or "SSL" in error_msg.upper():
            return "I'm experiencing SSL/certificate issues connecting to the AI service. Please contact support."
        elif "timeout" in error_msg.lower():
            return "The AI service request timed out. Please try again."
        else:
            return f"I'm experiencing technical difficulties processing your request."
