# Agent Architecture

## Overview

This agent is a CLI tool that connects to an LLM (Large Language Model) and answers questions. It serves as the foundation for more advanced agent capabilities in subsequent tasks.

## Architecture

```
┌─────────────┐     ┌──────────┐     ┌─────────────┐     ┌──────────┐
│  CLI Input  │ ──→ │ agent.py  │ ──→ │  LLM API    │ ──→ │  JSON    │
│  (question) │     │  (Python) │     │  (Qwen)     │     │  Output  │
└─────────────┘     └──────────┘     └─────────────┘     └──────────┘
```

## Components

### `agent.py`

The main entry point. Responsibilities:
- Parse command-line arguments
- Load configuration from `.env.agent.secret`
- Send HTTP request to LLM API
- Format and output JSON response

### Configuration (`.env.agent.secret`)

| Variable | Description |
|----------|-------------|
| `LLM_API_KEY` | API key for authentication |
| `LLM_API_BASE` | Base URL of the LLM API endpoint |
| `LLM_MODEL` | Model name (e.g., `qwen3-coder-plus`) |

## LLM Provider

**Provider:** Qwen Code API  
**Model:** `qwen3-coder-plus`  
**API Type:** OpenAI-compatible chat completions API

### Why Qwen Code?

- 1000 free requests per day
- Works from Russia
- No credit card required
- Strong tool-calling capabilities

## API Flow

1. **Request Format:**
   ```json
   POST {LLM_API_BASE}/chat/completions
   {
     "model": "qwen3-coder-plus",
     "messages": [{"role": "user", "content": "<question>"}]
   }
   ```

2. **Response Format:**
   ```json
   {
     "choices": [{
       "message": {"content": "<answer>"}
     }]
   }
   ```

3. **Output Format:**
   ```json
   {"answer": "<answer>", "tool_calls": []}
   ```

## Error Handling

| Error Type | Handling |
|------------|----------|
| Timeout (>60s) | RuntimeError with message |
| HTTP 4xx/5xx | RuntimeError with status code |
| Network errors | RuntimeError with details |
| Empty response | RuntimeError |
| Invalid JSON | Exception propagates |

All errors are logged to **stderr**, exit code is **1** on failure.

## Usage

```bash
# Basic usage
uv run agent.py "What does REST stand for?"

# Expected output (stdout)
{"answer": "Representational State Transfer.", "tool_calls": []}

# Debug output (stderr)
Loaded LLM configuration
Sending request to http://<vm-ip>:42005/v1/chat/completions
Model: qwen3-coder-plus
Received answer from LLM
```

## Testing

Run the regression test:

```bash
uv run pytest tests/test_agent.py -v
```

## Future Extensions

- **Task 2:** Add tool support (calculator, search, etc.)
- **Task 3:** Add agentic loop with tool selection
- **Task 4+:** Add domain knowledge from wiki
