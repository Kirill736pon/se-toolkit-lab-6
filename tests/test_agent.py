"""
Regression tests for agent.py

Tests verify that the agent outputs valid JSON with required fields.
"""

import json
import subprocess
import sys


def test_agent_output_format():
    """
    Test that agent.py outputs valid JSON with 'answer' and 'tool_calls' fields.

    This test runs the agent as a subprocess with a simple question and verifies:
    1. Exit code is 0 (success)
    2. Stdout is valid JSON
    3. JSON contains 'answer' field (string)
    4. JSON contains 'tool_calls' field (list)
    """
    # Run agent with a simple question
    result = subprocess.run(
        [sys.executable, "agent.py", "What is 2 + 2?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e

    # Check required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' cannot be empty"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be a list"
