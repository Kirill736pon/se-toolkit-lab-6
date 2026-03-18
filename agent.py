#!/usr/bin/env python3
"""
Agent CLI — connects to an LLM and answers questions using tools.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": "...", "tool_calls": [...]}
    Debug info to stderr.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """LLM configuration from .env.agent.secret."""

    model_config = SettingsConfigDict(
        env_file=".env.agent.secret",
        env_file_encoding="utf-8",
    )

    llm_api_key: str
    llm_api_base: str
    llm_model: str


class DockerSettings(BaseSettings):
    """Docker environment configuration from .env.docker.secret."""

    model_config = SettingsConfigDict(
        env_file=".env.docker.secret",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    lms_api_key: str = ""


class AgentSettings(BaseSettings):
    """Agent-specific environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env.agent.secret",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    agent_api_base_url: str = "http://localhost:42002"


# =============================================================================
# Tool definitions
# =============================================================================


def is_safe_path(path: str) -> bool:
    """
    Check if a path is safe (within project directory).

    Rejects paths containing '..' or absolute paths.
    Verifies the resolved path is within the project root.
    """
    if ".." in path:
        return False
    # Reject absolute paths (Unix or Windows style)
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        return False

    project_root = Path.cwd().resolve()
    try:
        full_path = (project_root / path).resolve()
        return full_path.is_relative_to(project_root)
    except (ValueError, TypeError):
        return False


def read_file(path: str) -> str:
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root.

    Returns:
        File contents as string, or error message.
    """
    if not is_safe_path(path):
        return f"Error: Access denied - path '{path}' is not allowed"

    project_root = Path.cwd().resolve()
    full_path = project_root / path

    if not full_path.exists():
        return f"Error: File not found - {path}"

    if not full_path.is_file():
        return f"Error: Not a file - {path}"

    try:
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error: Could not read file - {e}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root.

    Returns:
        Newline-separated listing of entries, or error message.
    """
    if not is_safe_path(path):
        return f"Error: Access denied - path '{path}' is not allowed"

    project_root = Path.cwd().resolve()
    full_path = project_root / path

    if not full_path.exists():
        return f"Error: Directory not found - {path}"

    if not full_path.is_dir():
        return f"Error: Not a directory - {path}"

    try:
        entries = sorted(full_path.iterdir())
        return "\n".join(entry.name for entry in entries)
    except Exception as e:
        return f"Error: Could not list directory - {e}"


def query_api(
    method: str,
    path: str,
    body: str | None = None,
    lms_api_key: str = "",
    api_base_url: str = "http://localhost:42002",
) -> str:
    """
    Query the backend API.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API endpoint path (e.g., '/items/', '/analytics/')
        body: Optional JSON request body for POST/PUT requests
        lms_api_key: API key for authentication (from LMS_API_KEY env var)
        api_base_url: Base URL of the backend API

    Returns:
        JSON string with status_code and body, or error message.
    """
    import httpx

    # Validate method
    valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    if method.upper() not in valid_methods:
        return f'Error: Invalid HTTP method "{method}". Valid methods: {", ".join(valid_methods)}'

    # Build URL
    base_url = api_base_url.rstrip("/")
    url = f"{base_url}{path}"

    # Prepare headers
    headers = {}
    if lms_api_key:
        headers["Authorization"] = f"Bearer {lms_api_key}"

    # Prepare request body
    json_body = None
    if body:
        try:
            json_body = json.loads(body)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON body - {e}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json_body,
            )

            result = {
                "status_code": response.status_code,
                "body": response.json() if response.content else None,
            }
            return json.dumps(result)

    except httpx.TimeoutException:
        return f"Error: Request to {url} timed out (30s limit)"
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} - {e.response.text[:200]}"
    except httpx.RequestError as e:
        return f"Error: Network error - {e}"
    except Exception as e:
        return f"Error: Unexpected error - {e}"


# Tool schemas for LLM function calling
TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the project repository",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories in a directory",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative directory path from project root (e.g., 'wiki')",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "query_api",
        "description": "Query the backend API to get data from the database (items, submissions, analytics, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "HTTP method (GET, POST, PUT, DELETE)",
                },
                "path": {
                    "type": "string",
                    "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')",
                },
                "body": {
                    "type": "string",
                    "description": "Optional JSON request body for POST/PUT requests",
                },
            },
            "required": ["method", "path"],
        },
    },
]

# System prompt for the documentation agent
SYSTEM_PROMPT = """You are a documentation and system assistant. You have access to three tools:
- list_files: List files in a directory
- read_file: Read a file's contents
- query_api: Query the backend API to get data from the database

To answer questions:
1. For wiki/documentation questions → use list_files and read_file
2. For system facts (framework, ports, code structure) → use read_file on source code
3. For data queries (item count, scores, analytics, submissions) → use query_api with GET/POST

Always include the source reference in your answer when using wiki files (format: "wiki/file.md#section-anchor").
For API queries, mention the endpoint used in your answer.
"""


def execute_tool(
    tool_name: str,
    args: dict[str, Any],
    lms_api_key: str = "",
    api_base_url: str = "http://localhost:42002",
) -> str:
    """
    Execute a tool call and return the result.

    Args:
        tool_name: Name of the tool to execute.
        args: Arguments for the tool.
        lms_api_key: API key for query_api authentication.
        api_base_url: Base URL for query_api.

    Returns:
        Tool result as string.
    """
    if tool_name == "read_file":
        path = args.get("path", "")
        return read_file(path)
    elif tool_name == "list_files":
        path = args.get("path", "")
        return list_files(path)
    elif tool_name == "query_api":
        method = args.get("method", "GET")
        path = args.get("path", "")
        body = args.get("body")
        return query_api(
            method=method,
            path=path,
            body=body,
            lms_api_key=lms_api_key,
            api_base_url=api_base_url,
        )
    else:
        return f"Error: Unknown tool '{tool_name}'"


def extract_source_from_answer(answer: str) -> str:
    """
    Extract source reference from the LLM answer.

    Looks for patterns like: wiki/file.md#section or wiki/file.md
    """
    # Pattern for wiki/file.md#anchor or wiki/file.md
    pattern = r"(wiki/[\w-]+\.md(?:#[\w-]+)?)"
    match = re.search(pattern, answer)
    if match:
        return match.group(1)
    return ""


def call_llm_with_tools(
    question: str,
    settings: Settings,
    docker_settings: DockerSettings,
    agent_settings: AgentSettings,
) -> dict[str, Any]:
    """
    Send a question to the LLM and execute tool calls in a loop.

    Returns:
        Dict with 'answer', 'source', and 'tool_calls' fields.
    """
    import httpx

    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    # Initialize conversation with system prompt and user question
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # Track all tool calls for output
    tool_calls_log: list[dict[str, Any]] = []

    # Agentic loop - max 10 iterations
    max_iterations = 10
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"Loop iteration {iteration}/{max_iterations}", file=sys.stderr)

        # Build payload with tools
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
        }

        print(f"Sending request to {url}", file=sys.stderr)
        print(f"Model: {settings.llm_model}", file=sys.stderr)

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            raise RuntimeError("LLM request timed out (60s limit)")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"LLM API error: {e.response.status_code} {e.response.text}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Network error: {e}")

        if "choices" not in data or not data["choices"]:
            raise RuntimeError("Invalid response from LLM: no choices")

        choice = data["choices"][0]
        message = choice["message"]

        # Check for tool calls
        tool_calls = message.get("tool_calls")

        if tool_calls:
            print(f"LLM requested {len(tool_calls)} tool call(s)", file=sys.stderr)

            # First, append the assistant's message with tool_calls
            messages.append({
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": tool_calls,
            })

            # Execute each tool call
            for tool_call in tool_calls:
                tool_id = tool_call["id"]
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])

                print(f"Executing tool: {tool_name}({tool_args})", file=sys.stderr)

                # Execute the tool
                result = execute_tool(
                    tool_name,
                    tool_args,
                    lms_api_key=docker_settings.lms_api_key,
                    api_base_url=agent_settings.agent_api_base_url,
                )

                # Log for output
                tool_calls_log.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result,
                })

                # Append tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result,
                })

            # Continue loop - LLM will process tool results
            continue
        else:
            # No tool calls - this is the final answer
            answer = message.get("content", "")
            if not answer:
                raise RuntimeError("LLM returned empty answer")

            print(f"Received final answer from LLM", file=sys.stderr)

            # Extract source reference
            source = extract_source_from_answer(answer)

            # Build result
            result: dict[str, Any] = {
                "answer": answer,
                "source": source,
                "tool_calls": tool_calls_log,
            }

            return result

    # Max iterations reached
    print("Warning: Max iterations reached", file=sys.stderr)
    return {
        "answer": "I reached the maximum number of tool calls (10) without finding a complete answer.",
        "source": "",
        "tool_calls": tool_calls_log,
    }


def main() -> int:
    """Main entry point."""
    # Validate command-line arguments
    if len(sys.argv) != 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        return 1

    question = sys.argv[1]

    if not question.strip():
        print("Error: Question cannot be empty", file=sys.stderr)
        return 1

    try:
        # Load settings from all config files
        settings = Settings()  # type: ignore[call-arg]
        docker_settings = DockerSettings()  # type: ignore[call-arg]
        agent_settings = AgentSettings()  # type: ignore[call-arg]
        print(f"Loaded LLM configuration", file=sys.stderr)
        print(f"Loaded LMS API key: {'yes' if docker_settings.lms_api_key else 'no'}", file=sys.stderr)
        print(f"Loaded API base URL: {agent_settings.agent_api_base_url}", file=sys.stderr)

        # Call LLM with tools
        result = call_llm_with_tools(question, settings, docker_settings, agent_settings)

        # Output valid JSON to stdout
        print(json.dumps(result))

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
