# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM and answers questions using tools. It implements an **agentic loop** that allows the LLM to call tools (`read_file`, `list_files`) to navigate the project wiki and provide answers with source references.

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
- Load configuration from `.env.agent.secret`
- Execute agentic loop with tool calls
- Format and output JSON response

### Tools

Two tools are implemented for wiki navigation:

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

### Tool Schemas (OpenAI Format)

Tools are registered with the LLM using function-calling schemas:

```json
{
  "name": "read_file",
  "description": "Read a file from the project repository",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root"
      }
    },
    "required": ["path"]
  }
}
```

### System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to discover wiki structure
2. Use `read_file` to find relevant sections
3. Include source reference in answer (format: `wiki/file.md#section-anchor`)

```
You are a documentation assistant. You have access to two tools:
- list_files: List files in a directory
- read_file: Read a file's contents

To answer questions:
1. First explore the wiki structure with list_files if needed
2. Read relevant files with read_file to find the answer
3. Answer the question and include a source reference in the format: "wiki/file.md#section-anchor"

Always include the source reference in your answer.
```

### Configuration (`.env.agent.secret`)

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | API key for authentication |
| `LLM_API_BASE` | Base URL of the LLM API endpoint |
| `LLM_MODEL` | Model name (e.g., `qwen3-coder-plus`) |

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
            "name": "read_file",
            "arguments": "{\"path\": \"wiki/git-workflow.md\"}"
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
  "content": "<file contents>"
}
```

### Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
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
| Timeout (>60s) | RuntimeError with message |
| HTTP 4xx/5xx | RuntimeError with status code |
| Network errors | RuntimeError with details |
| Empty response | RuntimeError |
| Max iterations (10) | Return partial answer with warning |

All errors are logged to **stderr**, exit code is **1** on failure.

## Usage

```bash
# Basic usage with tools
uv run agent.py "How do you resolve a merge conflict?"

# Expected output (stdout)
{
  "answer": "Edit the conflicting file...",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [...]
}

# Debug output (stderr)
Loaded LLM configuration
Loop iteration 1/10
Sending request to http://<vm-ip>:42005/v1/chat/completions
Model: qwen3-coder-plus
LLM requested 1 tool call(s)
Executing tool: list_files({'path': 'wiki'})
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
