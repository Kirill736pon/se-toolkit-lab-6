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


def test_read_file_tool_usage():
    """
    Test that agent uses read_file tool for wiki questions.

    Question: "How do you resolve a merge conflict?"
    Expected:
    - read_file in tool_calls
    - wiki/git-vscode.md or wiki/git.md in source field (contains merge conflict info)
    """
    result = subprocess.run(
        [sys.executable, "agent.py", "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "source" in output, "Missing 'source' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Verify read_file was used
    tool_names = [tc.get("tool") for tc in output["tool_calls"]]
    assert "read_file" in tool_names, "Expected 'read_file' in tool_calls"

    # Verify source contains wiki/git-vscode.md or wiki/git.md
    source = output["source"]
    assert "wiki/git-vscode.md" in source or "wiki/git.md" in source, (
        f"Expected 'wiki/git-vscode.md' or 'wiki/git.md' in source, got: {source}"
    )


def test_list_files_tool_usage():
    """
    Test that agent uses list_files tool for directory listing questions.

    Question: "What files are in the wiki?"
    Expected:
    - list_files in tool_calls
    """
    result = subprocess.run(
        [sys.executable, "agent.py", "What files are in the wiki?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"

    # Parse stdout as JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {result.stdout}") from e

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field in output"
    assert "tool_calls" in output, "Missing 'tool_calls' field in output"

    # Verify list_files was used
    tool_names = [tc.get("tool") for tc in output["tool_calls"]]
    assert "list_files" in tool_names, "Expected 'list_files' in tool_calls"
