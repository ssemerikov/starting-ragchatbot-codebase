import json
from openai import OpenAI
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with OpenRouter API using OpenAI-compatible interface"""

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
- **One tool call per query maximum**
- Synthesize tool results into accurate, fact-based responses
- If tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course outline/structure questions**: Use get_course_outline tool
- **Course content questions**: Use search_course_content tool
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool usage explanations, or question-type analysis
 - Do not mention "based on the search results" or "based on the course outline"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, base_url: str, model: str, fallback_models: List[str]):
        """
        Initialize OpenAI client for OpenRouter.

        Args:
            api_key: OpenRouter API key
            base_url: OpenRouter API base URL
            model: Default model to use
            fallback_models: Priority-ordered list of fallback models
        """
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
            "messages": messages,
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
                    # All models failed
                    return f"Error: All models failed. Last error with {model}: {error_msg}"

        return "Error: No models available to process request"

    def _handle_tool_execution(self, initial_response, messages: List[Dict],
                               base_params: Dict[str, Any], tool_manager) -> str:
        """
        Handle execution of tool calls and get follow-up response.

        Args:
            initial_response: The response containing tool calls
            messages: Current message history
            base_params: Base API parameters
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution
        """
        # Get tool calls from response
        tool_calls = initial_response.choices[0].message.tool_calls

        if not tool_calls:
            return initial_response.choices[0].message.content or ""

        # Add assistant's response with tool calls to messages
        assistant_message = {
            "role": "assistant",
            "content": initial_response.choices[0].message.content,
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

        # Execute all tool calls and collect results
        for tool_call in tool_calls:
            # Parse arguments (OpenAI returns JSON string)
            try:
                tool_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            # Execute tool
            tool_result = tool_manager.execute_tool(
                tool_call.function.name,
                **tool_args
            )

            # Add tool result as separate message with role "tool"
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

        # Prepare final API call without tools
        final_params = {
            **self.base_params,
            "messages": messages,
            "model": base_params["model"]
        }

        # Get final response (with fallback)
        models_to_try = [base_params["model"]] + [m for m in self.fallback_models if m != base_params["model"]]

        for model in models_to_try:
            try:
                final_params["model"] = model
                final_response = self.client.chat.completions.create(**final_params)
                self.last_model_used = model
                return final_response.choices[0].message.content or ""
            except Exception as e:
                if model == models_to_try[-1]:
                    return f"Error getting final response: {str(e)}"
                continue

        return "Error: Could not get final response from any model"
