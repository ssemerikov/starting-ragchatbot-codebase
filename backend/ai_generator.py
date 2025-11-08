import json
from openai import OpenAI
from typing import List, Optional, Dict, Any
import httpx
import ssl
import certifi

class AIGenerator:
    """Handles interactions with OpenRouter API using OpenAI-compatible interface"""

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

    def __init__(self, api_key: str, base_url: str, model: str, fallback_models: List[str]):
        """
        Initialize OpenAI client for OpenRouter with proper SSL configuration.

        Args:
            api_key: OpenRouter API key
            base_url: OpenRouter API base URL
            model: Default model to use
            fallback_models: Priority-ordered list of fallback models
        """
        # Create SSL context with certifi certificates for proper verification
        try:
            ssl_context = ssl.create_default_context(cafile=certifi.where())

            # Create HTTP client with proper SSL configuration
            http_client = httpx.Client(
                verify=ssl_context,
                timeout=60.0  # 60 second timeout
            )

            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                http_client=http_client
            )
        except Exception as e:
            # Fallback to default client if SSL configuration fails
            print(f"Warning: Could not configure SSL with certifi, using default: {e}")
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )

        self.current_model = model
        self.fallback_models = fallback_models
        self.last_model_used = model

        # Pre-build base API parameters
        self.base_params = {
            "temperature": 0,
            "max_tokens": 800
        }

    def set_model(self, model: str) -> None:
        """Change the active model"""
        self.current_model = model

    def get_current_model(self) -> str:
        """Return the currently active model"""
        return self.current_model

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Uses auto-fallback if model fails.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """
        # Build messages with system prompt as first message
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": query}
        ]

        # Prepare API call parameters
        api_params = {
            **self.base_params,
            "messages": messages.copy(),  # Copy to avoid reference issues
            "model": self.current_model
        }

        # Add tools if available (OpenAI format)
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = "auto"

        # Try with auto-fallback
        models_to_try = [self.current_model] + [m for m in self.fallback_models if m != self.current_model]

        for model_index, model in enumerate(models_to_try):
            try:
                api_params["model"] = model
                response = self.client.chat.completions.create(**api_params)

                # Update last successful model
                self.last_model_used = model

                # Handle tool execution if needed
                if response.choices[0].finish_reason == "tool_calls" and tool_manager:
                    return self._handle_tool_execution(response, messages, api_params, tool_manager)

                # Return direct response
                return response.choices[0].message.content or ""

            except Exception as e:
                error_msg = str(e)
                # If this isn't the last model to try, continue to next
                if model_index < len(models_to_try) - 1:
                    continue
                else:
                    # All models failed - provide user-friendly message
                    if "Connection error" in error_msg or "connect" in error_msg.lower():
                        return "I'm unable to connect to the AI service. Please check your network connection or try again later."
                    elif "CERTIFICATE" in error_msg.upper() or "SSL" in error_msg.upper():
                        return "I'm experiencing SSL/certificate issues connecting to the AI service. Please contact support."
                    elif "timeout" in error_msg.lower():
                        return "The AI service request timed out. Please try again."
                    else:
                        return f"I'm experiencing technical difficulties. Error: {error_msg[:100]}"

        return "I'm unable to process your request. No AI models are currently available."

    def _handle_tool_execution(self, initial_response, messages: List[Dict],
                               base_params: Dict[str, Any], tool_manager) -> str:
        """
        Handle execution of tools with support for sequential rounds.
        Allows Claude to make multiple tool calls across up to MAX_TOOL_ROUNDS rounds.

        Architecture:
        - Round 1: Initial tool call(s) + results → API call WITH tools
        - Round 2: Optional second tool call(s) + results → API call WITHOUT tools
        - Terminates early if Claude doesn't use tools

        Args:
            initial_response: First response containing tool calls
            messages: Current message history [system, user]
            base_params: Base API parameters including tools
            tool_manager: Manager to execute tools

        Returns:
            Final response text after all rounds
        """
        current_round = 0
        current_response = initial_response

        # Main iteration loop
        while current_round < self.MAX_TOOL_ROUNDS:
            current_round += 1

            # Check if this response has tool calls
            tool_calls = current_response.choices[0].message.tool_calls

            if not tool_calls:
                # Natural termination - Claude chose not to use tools
                return current_response.choices[0].message.content or ""

            # Process this round of tool calls
            messages = self._process_tool_round(
                current_response,
                messages,
                tool_manager
            )

            # Determine if tools should be available for next round
            should_include_tools = (current_round < self.MAX_TOOL_ROUNDS)

            # Build parameters for next API call
            next_params = self._build_round_params(
                base_params,
                messages,
                include_tools=should_include_tools
            )

            # Make next API call (with fallback handling)
            try:
                current_response = self._make_api_call_with_fallback(
                    next_params,
                    base_params["model"]
                )
            except Exception as e:
                # Error handling - return partial results if available
                return self._handle_api_error(e, messages, current_round)

        # Max rounds reached - return final response
        return current_response.choices[0].message.content or ""

    def _process_tool_round(self, response, messages: List[Dict], tool_manager) -> List[Dict]:
        """
        Process a single round of tool calling and accumulate results.

        Args:
            response: API response with tool calls
            messages: Current message list
            tool_manager: Tool execution manager

        Returns:
            Updated messages list with assistant message and tool results
        """
        tool_calls = response.choices[0].message.tool_calls

        # Add assistant's message with tool calls
        assistant_message = {
            "role": "assistant",
            "content": response.choices[0].message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in tool_calls
            ]
        }
        messages.append(assistant_message)

        # Execute each tool and add results
        for tool_call in tool_calls:
            # Parse arguments (OpenAI returns JSON string)
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            # Execute tool
            try:
                tool_result = tool_manager.execute_tool(
                    tool_call.function.name,
                    **tool_args
                )
            except Exception as e:
                # Individual tool failure - add error message as result
                tool_result = f"Error executing tool: {str(e)}"

            # Add tool result message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

        return messages

    def _build_round_params(self, base_params: Dict, messages: List[Dict],
                           include_tools: bool) -> Dict[str, Any]:
        """
        Build API parameters for a round with conditional tool inclusion.

        Args:
            base_params: Base parameters (temperature, max_tokens, tools)
            messages: Current message history
            include_tools: Whether to include tool definitions

        Returns:
            Complete API call parameters
        """
        params = {
            **self.base_params,
            "messages": messages.copy(),  # Copy to avoid reference issues
            "model": base_params["model"]
        }

        if include_tools and "tools" in base_params:
            # Tools available - Claude can call them
            params["tools"] = base_params["tools"]
            params["tool_choice"] = "auto"
        # else: No tools - Claude must provide final answer

        return params

    def _make_api_call_with_fallback(self, api_params: Dict[str, Any], primary_model: str):
        """
        Make API call with fallback model support.

        Args:
            api_params: API call parameters
            primary_model: Primary model to try

        Returns:
            API response

        Raises:
            Exception: If all models fail
        """
        models_to_try = [primary_model] + [m for m in self.fallback_models if m != primary_model]

        for model_index, model in enumerate(models_to_try):
            try:
                api_params["model"] = model
                response = self.client.chat.completions.create(**api_params)
                self.last_model_used = model
                return response

            except Exception as e:
                # If this isn't the last model to try, continue to next
                if model_index < len(models_to_try) - 1:
                    continue
                else:
                    # All models failed
                    raise

        raise Exception("All models failed")

    def _handle_api_error(self, error: Exception, messages: List[Dict], round_num: int) -> str:
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
