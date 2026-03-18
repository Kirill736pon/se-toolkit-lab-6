#!/usr/bin/env python3
"""
Agent CLI — connects to an LLM and answers questions.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": []}
    Debug info to stderr.
"""

import json
import sys
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


def call_llm(question: str, settings: Settings) -> str:
    """
    Send a question to the LLM and return the answer.

    Uses OpenAI-compatible chat completions API.
    """
    import httpx

    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": question}],
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

    answer = data["choices"][0]["message"]["content"]
    if not answer:
        raise RuntimeError("LLM returned empty answer")

    print(f"Received answer from LLM", file=sys.stderr)
    return answer


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
        # Load settings
        settings = Settings()  # type: ignore[call-arg]
        print(f"Loaded LLM configuration", file=sys.stderr)

        # Call LLM
        answer = call_llm(question, settings)

        # Format output
        result: dict[str, Any] = {
            "answer": answer,
            "tool_calls": [],
        }

        # Output valid JSON to stdout
        print(json.dumps(result))

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
