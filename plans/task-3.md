# Task 3 Implementation Plan: The System Agent

## Overview

This task extends the agent from Task 2 with a new `query_api` tool that allows the LLM to query the deployed backend API. The agent will answer two types of questions:

1. **Static system facts** — framework, ports, status codes (requires reading source code or wiki)
2. **Data-dependent queries** — item count, scores, analytics (requires calling the backend API)

## Tool Schema: `query_api`

### Parameters

| Parameter | Type   | Required | Description                                      |
|-----------|--------|----------|--------------------------------------------------|
| `method`  | string | yes      | HTTP method (GET, POST, PUT, DELETE, etc.)       |
| `path`    | string | yes      | API endpoint path (e.g., `/items/`, `/analytics`)|
| `body`    | string | no       | JSON request body for POST/PUT requests          |

### Return Value

JSON string with the following structure:

```json
{
  "status_code": 200,
  "body": { ... }
}
```

### Implementation Details

1. **HTTP Client**: Use `httpx` (already in dependencies) to make HTTP requests
2. **Authentication**: Read `LMS_API_KEY` from environment and send as `Authorization: Bearer <key>`
3. **Base URL**: Read `AGENT_API_BASE_URL` from environment, default to `http://localhost:42002`
4. **Error Handling**: Catch timeouts, HTTP errors, and network errors; return descriptive error messages

## Environment Variables

The agent must read all configuration from environment variables (not hardcoded):

| Variable             | Purpose                                      | Source File          |
|----------------------|----------------------------------------------|----------------------|
| `LLM_API_KEY`        | LLM provider API key                         | `.env.agent.secret`  |
| `LLM_API_BASE`       | LLM API endpoint URL                         | `.env.agent.secret`  |
| `LLM_MODEL`          | Model name                                   | `.env.agent.secret`  |
| `LMS_API_KEY`        | Backend API key for `query_api` auth         | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for backend (default: localhost)    | Optional, env only   |

### Settings Class Update

Extend the `Settings` class to include:

- `lms_api_key` (from `.env.docker.secret`)
- `agent_api_base_url` (optional, with default)

Note: Need to handle multiple env files or load `LMS_API_KEY` separately.

## System Prompt Update

Update the system prompt to guide the LLM on when to use each tool:

```
You are a documentation and system assistant. You have access to these tools:
- list_files: List files in a directory
- read_file: Read a file's contents
- query_api: Query the backend API

To answer questions:
1. For wiki/documentation questions → use list_files and read_file
2. For system facts (framework, ports, code structure) → use read_file on source code
3. For data queries (item count, scores, analytics) → use query_api with GET/POST

Always include the source reference in your answer when using wiki files.
For API queries, mention the endpoint used.
```

## Implementation Steps

### Step 1: Add Environment Variables

1. Create `.env.agent.secret` with LLM credentials
2. Create `.env.docker.secret` with `LMS_API_KEY`
3. Update `Settings` class to load both files or load `LMS_API_KEY` separately

### Step 2: Implement `query_api` Function

```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Query the backend API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path
        body: Optional JSON request body
        
    Returns:
        JSON string with status_code and body
    """
    # Implementation with httpx
```

### Step 3: Register Tool Schema

Add `query_api` to the `TOOLS` list with proper parameter definitions.

### Step 4: Update `execute_tool`

Add a case for `query_api` that calls the new function.

### Step 5: Update System Prompt

Modify `SYSTEM_PROMPT` to include guidance on using `query_api`.

### Step 6: Test Locally

1. Deploy backend on VM
2. Populate database via ETL sync
3. Test `query_api` manually:

   ```bash
   uv run agent.py "How many items are in the database?"
   ```

### Step 7: Run Benchmark

```bash
uv run run_eval.py
```

Iterate on failures:

- If tool not called → improve tool description
- If wrong arguments → clarify parameter descriptions
- If error → fix implementation

## Testing Strategy

### New Tests to Add

1. **Test: System fact question**
   - Question: "What framework does the backend use?"
   - Expected: `read_file` in tool_calls (reads backend source)
   - Verifies: Agent uses file reading for static facts

2. **Test: Data query question**
   - Question: "How many items are in the database?"
   - Expected: `query_api` in tool_calls with GET /items/
   - Verifies: Agent uses API for data queries

### Running Tests

```bash
uv run pytest tests/test_agent.py -v
```

## Benchmark Diagnosis (to be filled after first run)

**Note:** Running `run_eval.py` requires:

1. Deployed backend on VM with populated database
2. Valid LLM API credentials in `.env.agent.secret`

### Setup Steps Required

1. **On your VM:**

   ```bash
   ssh <vm-user>@<vm-ip>
   cd ~/se-toolkit-lab-6
   docker compose --env-file .env.docker.secret up --build -d
   ```

2. **Populate database:**
   - Open `http://<vm-ip>:42002/docs`
   - Authorize with your `LMS_API_KEY`
   - Call `POST /pipeline/sync`

3. **Configure LLM credentials:**
   - Edit `.env.agent.secret`
   - Set `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`

4. **Run benchmark:**

   ```bash
   uv run run_eval.py
   ```

Initial score: _will fill after running with valid credentials_

First failures:

- _will document actual failures_

Iteration strategy:

1. Fix tool description if LLM doesn't call it
2. Fix implementation if tool returns errors
3. Adjust system prompt if LLM confuses tools

## Acceptance Criteria Checklist

- [ ] `query_api` defined as function-calling schema
- [ ] `query_api` authenticates with `LMS_API_KEY`
- [ ] Agent reads LLM config from env vars
- [ ] Agent reads `AGENT_API_BASE_URL` from env
- [ ] Static system questions answered correctly
- [ ] Data-dependent questions answered with API
- [ ] `run_eval.py` passes all 10 questions
- [ ] 2 new regression tests added
- [ ] `AGENT.md` updated (200+ words)
