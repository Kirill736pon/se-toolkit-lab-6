# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM and answers questions using tools. It implements an **agentic loop** that allows the LLM to call tools (`read_file`, `list_files`, `query_api`) to navigate the project wiki, query the backend API, and provide answers with source references.

## Architecture

### High-Level Flow

```
┌─────────────┐     ┌──────────┐     ┌─────────────┐     ┌──────────┐
│  CLI Input  │ ──→ │ agent.py  │ ──→ │  LLM API    │ ──→ │  JSON     │
│  (question) │     │  (Python) │     │  (Qwen)     │     │  Output   │
└─────────────┘     └──────────┘     └─────────────┘     └──────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   Tools     │
                   │ read_file   │
                   │ list_files  │
                   │ query_api   │
                   └─────────────┘
```

### Agentic Loop

```
Question ──▶ LLM ──▶ tool call? ──yes──▶ execute tool ──▶ back to LLM
                         │
                         no
                         │
                         ▼
                    JSON output
```

1. Send user question + tool definitions to LLM
2. If LLM responds with `tool_calls` → execute each tool, append results as `tool` role messages, repeat
3. If LLM responds with text (no tool calls) → extract answer and source, output JSON
4. Maximum 10 tool calls per question

## Components

### `agent.py`

The main entry point. Responsibilities:

- Parse command-line arguments
- Load configuration from `.env.agent.secret` and `.env.docker.secret`
- Execute agentic loop with tool calls
- Format and output JSON response

### Tools

Three tools are implemented:

#### `read_file`

Read a file from the project repository.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Relative path from project root (e.g., `wiki/git-workflow.md`) |

**Returns:** File contents as string, or error message.

**Security:** Rejects paths containing `..` or absolute paths. Verifies resolved path is within project root.

#### `list_files`

List files and directories at a given path.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Relative directory path from project root (e.g., `wiki`) |

**Returns:** Newline-separated listing of entries, or error message.

**Security:** Same as `read_file`.

#### `query_api` (Task 3)

Query the backend API to retrieve data from the database.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `method` | string | yes | HTTP method (GET, POST, PUT, DELETE, etc.) |
| `path` | string | yes | API endpoint path (e.g., `/items/`, `/analytics/`) |
| `body` | string | no | JSON request body for POST/PUT requests |

**Returns:** JSON string with `status_code` and `body`, or error message.

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret` as Bearer token.

**Base URL:** Read from `AGENT_API_BASE_URL` environment variable (default: `http://localhost:42002`).

**Error Handling:**

- Timeout (30s) → descriptive error message
- HTTP errors (4xx, 5xx) → status code and response body
- Network errors → connection error details
- Invalid JSON body → parse error message

### Tool Schemas (OpenAI Format)

Tools are registered with the LLM using function-calling schemas:

```json
{
  "name": "query_api",
  "description": "Query the backend API to get data from the database (items, submissions, analytics, etc.)",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE)"
      },
      "path": {
        "type": "string",
        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT requests"
      }
    },
    "required": ["method", "path"]
  }
}
```

### System Prompt

The system prompt instructs the LLM to use the appropriate tool based on question type:

```
You are a documentation and system assistant. You have access to three tools:
- list_files: List files in a directory
- read_file: Read a file's contents
- query_api: Query the backend API to get data from the database

To answer questions:
1. For wiki/documentation questions → use list_files and read_file
2. For system facts (framework, ports, code structure) → use read_file on source code
3. For data queries (item count, scores, analytics, submissions) → use query_api with GET/POST

Always include the source reference in your answer when using wiki files (format: "wiki/file.md#section-anchor").
For API queries, mention the endpoint used in your answer.
```

### Configuration

#### `.env.agent.secret` (LLM configuration)

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | API key for authentication with LLM provider |
| `LLM_API_BASE` | Base URL of the LLM API endpoint |
| `LLM_MODEL` | Model name (e.g., `qwen3-coder-plus`) |
| `AGENT_API_BASE_URL` | Optional: Base URL for backend API (default: `http://localhost:42002`) |

#### `.env.docker.secret` (Backend configuration)

| Variable | Description |
|----------|-------------|
| `LMS_API_KEY` | Backend API key for `query_api` authentication |

**Important:** Two distinct keys:

- `LMS_API_KEY` (in `.env.docker.secret`) protects your backend endpoints
- `LLM_API_KEY` (in `.env.agent.secret`) authenticates with your LLM provider

Don't mix them up!

## LLM Provider

**Provider:** Qwen Code API
**Model:** `qwen3-coder-plus`
**API Type:** OpenAI-compatible chat completions API with tool support

### Why Qwen Code?

- 1000 free requests per day
- Works from Russia
- No credit card required
- Strong tool-calling capabilities

## API Flow

### Request with Tools

```json
POST {LLM_API_BASE}/chat/completions
{
  "model": "qwen3-coder-plus",
  "messages": [
    {"role": "system", "content": "<system prompt>"},
    {"role": "user", "content": "<question>"}
  ],
  "tools": [...],
  "tool_choice": "auto"
}
```

### Tool Call Response

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "tool_calls": [
        {
          "id": "call_123",
          "type": "function",
          "function": {
            "name": "query_api",
            "arguments": "{\"method\": \"GET\", \"path\": \"/items/\"}"
          }
        }
      ]
    }
  }]
}
```

### Tool Result Message

After executing the tool, append result to messages:

```json
{
  "role": "tool",
  "tool_call_id": "call_123",
  "content": "{\"status_code\": 200, \"body\": [...]}"
}
```

### Output Format

```json
{
  "answer": "There are 120 items in the database.",
  "source": "",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": [...]}"
    }
  ]
}
```

## Path Security

**Threat model:** User or LLM might try to access files outside project directory.

**Mitigation:**

1. Reject paths containing `..` (path traversal)
2. Reject absolute paths (Unix `/` or Windows `C:`)
3. Use `Path.resolve()` to get absolute path
4. Verify resolved path starts with project root

```python
def is_safe_path(path: str) -> bool:
    if ".." in path or path.startswith("/"):
        return False
    project_root = Path.cwd().resolve()
    full_path = (project_root / path).resolve()
    return full_path.is_relative_to(project_root)
```

## Error Handling

| Error Type | Handling |
|------------|----------|
| Timeout (>60s LLM, >30s API) | RuntimeError with message |
| HTTP 4xx/5xx | RuntimeError with status code |
| Network errors | RuntimeError with details |
| Empty response | RuntimeError |
| Max iterations (10) | Return partial answer with warning |

All errors are logged to **stderr**, exit code is **1** on failure.

## Usage

```bash
# Basic usage with tools
uv run agent.py "How many items are in the database?"

# Expected output (stdout)
{
  "answer": "There are 120 items in the database.",
  "tool_calls": [
    {"tool": "query_api", "args": {"method": "GET", "path": "/items/"}, "result": "..."}
  ]
}

# Debug output (stderr)
Loaded LLM configuration
Loaded LMS API key: yes
Loaded API base URL: http://localhost:42002
Loop iteration 1/10
Sending request to http://<vm-ip>:42005/v1/chat/completions
Model: qwen3-coder-plus
LLM requested 1 tool call(s)
Executing tool: query_api({'method': 'GET', 'path': '/items/'})
Received final answer from LLM
```

## Testing

Run regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

**Tests:**

1. `test_agent_output_format` — verifies JSON structure
2. `test_read_file_tool_usage` — verifies `read_file` tool usage for wiki questions
3. `test_list_files_tool_usage` — verifies `list_files` tool usage for directory questions
4. `test_query_api_tool_usage_for_data` — verifies `query_api` usage for data queries
5. `test_read_file_for_system_facts` — verifies `read_file` usage for static facts

## Lessons Learned (Task 3)

### Tool Design

1. **Clear descriptions matter**: The LLM needs precise tool descriptions to know when to use each tool. Initially, I had vague descriptions and the LLM would try to use `read_file` for data queries.

2. **Authentication separation**: Keeping `LMS_API_KEY` separate from `LLM_API_KEY` is crucial. The backend API key authorizes data access, while the LLM key authenticates with the provider.

3. **Environment variable flexibility**: Reading `AGENT_API_BASE_URL` from environment allows the autochecker to inject its own backend URL during evaluation.

### Debugging Challenges

1. **Tool call loops**: If the LLM doesn't understand the tool result, it may call the same tool repeatedly. Limiting iterations to 10 prevents infinite loops.

2. **Error messages**: Returning descriptive error messages from tools helps the LLM understand what went wrong and potentially retry with corrected arguments.

3. **None vs missing content**: When the LLM returns `content: null` (not missing), using `(msg.get("content") or "")` instead of `msg.get("content", "")` prevents `AttributeError`.

### Benchmark Results

Initial testing showed the agent correctly:

- Uses `query_api` for data-dependent questions (item count, scores)
- Uses `read_file` for static system facts (framework, ports)
- Uses `list_files` and `read_file` for wiki documentation questions

Final eval score: **To be filled after running full benchmark with deployed backend**

## Future Improvements

1. **Caching**: Cache API responses to reduce redundant calls
2. **Retry logic**: Add exponential backoff for transient API errors
3. **Streaming**: Support streaming responses for long-running queries
4. **Tool composition**: Allow the LLM to chain multiple tool calls in a single iteration
