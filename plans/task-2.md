# Plan for Task 2: The Documentation Agent

## Overview

This plan describes how to implement the agentic loop with `read_file` and `list_files` tools, enabling the agent to navigate the wiki and answer questions with source references.

## Tool Schemas

### `read_file`

**Purpose:** Read a file from the project repository.

**Schema (OpenAI function calling format):**
```json
{
  "name": "read_file",
  "description": "Read a file from the project repository",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Accept `path` parameter (relative to project root)
- Security check: reject paths containing `..` or absolute paths
- Verify resolved path is within project directory using `Path.resolve()`
- Return file contents as string, or error message if file doesn't exist

### `list_files`

**Purpose:** List files and directories at a given path.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories in a directory",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root (e.g., 'wiki')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Accept `path` parameter (relative directory)
- Security check: same as `read_file`
- Return newline-separated listing of entries
- Handle errors (directory doesn't exist, not a directory, etc.)

## Agentic Loop

The loop follows this flow:

```
Question ──▶ LLM ──▶ tool call? ──yes──▶ execute tool ──▶ back to LLM
                         │
                         no
                         │
                         ▼
                    JSON output
```

### Step-by-step implementation:

1. **Initialize messages list** with system prompt + user question
   - System prompt instructs LLM to use tools and include source references

2. **Loop (max 10 iterations):**
   a. Call LLM with `tools` parameter and current messages
   b. Parse response:
      - If `tool_calls` present → execute each tool, append results as `tool` role messages, continue loop
      - If no tool calls → extract answer and source, break loop

3. **Execute tool call:**
   - Match tool name to function (`read_file` or `list_files`)
   - Call function with parsed arguments
   - Store result for returning to LLM and for output JSON

4. **Build output JSON:**
   - `answer`: extracted from final LLM message
   - `source`: extracted from answer (file path + section anchor)
   - `tool_calls`: list of all tool calls with `tool`, `args`, `result`

## Path Security

**Threat model:** User or LLM might try to access files outside project directory.

**Mitigation strategy:**
1. Reject any path containing `..` (path traversal attempt)
2. Reject absolute paths (start with `/` or drive letter on Windows)
3. Use `Path.resolve()` to get absolute path
4. Verify resolved path starts with project root path
5. Return error message like "Access denied: path outside project directory"

**Implementation:**
```python
def is_safe_path(path: str) -> bool:
    """Check if path is safe (within project directory)."""
    if ".." in path or path.startswith("/"):
        return False
    project_root = Path.cwd().resolve()
    try:
        full_path = (project_root / path).resolve()
        return full_path.is_relative_to(project_root)
    except (ValueError, TypeError):
        return False
```

## System Prompt Strategy

The system prompt should instruct the LLM to:

1. Use `list_files` to discover wiki structure
2. Use `read_file` to find relevant sections
3. Include source reference in answer (format: `wiki/file.md#section-anchor`)
4. Stop calling tools once enough information is found

Example system prompt:
```
You are a documentation assistant. You have access to two tools:
- list_files: List files in a directory
- read_file: Read a file's contents

To answer questions:
1. First explore the wiki structure with list_files if needed
2. Read relevant files with read_file
3. Answer the question and include a source reference (e.g., "wiki/git-workflow.md#resolving-merge-conflicts")

Always include the source reference in your answer.
```

## Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "git-workflow.md\n..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

## Testing Strategy

Two regression tests:

1. **Test `read_file` usage:**
   - Question: "How do you resolve a merge conflict?"
   - Expected: `read_file` in tool_calls, `wiki/git-workflow.md` in source

2. **Test `list_files` usage:**
   - Question: "What files are in the wiki?"
   - Expected: `list_files` in tool_calls

Tests will run `agent.py` as subprocess and verify JSON output structure.

## Implementation Order

1. Create this plan file
2. Implement `read_file` and `list_files` functions with security checks
3. Define tool schemas for LLM
4. Implement agentic loop in `call_llm` or new function
5. Update output format to include `source` and populate `tool_calls`
6. Update `AGENT.md` documentation
7. Write regression tests
8. Run tests and verify acceptance criteria
