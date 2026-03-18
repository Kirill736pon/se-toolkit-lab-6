#!/usr/bin/env python3
"""
Local test for query_api function.

Tests the query_api implementation without requiring LLM API.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import query_api


def test_query_api_invalid_method():
    """Test that invalid HTTP method returns error."""
    result = query_api(method="INVALID", path="/items/")
    assert "Error" in result
    assert "Invalid HTTP method" in result
    print("✓ Invalid method test passed")


def test_query_api_connection_error():
    """Test that connection error is handled gracefully."""
    # This will fail because backend is not running locally
    result = query_api(
        method="GET",
        path="/items/",
        api_base_url="http://localhost:42002"
    )
    # Should return error message, not crash
    assert "Error" in result
    print(f"✓ Connection error test passed: {result[:80]}...")


def test_query_api_invalid_json_body():
    """Test that invalid JSON body returns error."""
    result = query_api(
        method="POST",
        path="/items/",
        body="not valid json",
        api_base_url="http://localhost:42002"
    )
    assert "Error" in result
    assert "Invalid JSON body" in result
    print("✓ Invalid JSON body test passed")


def test_query_api_valid_body():
    """Test that valid JSON body is parsed correctly."""
    # This will fail with connection error, but body should be parsed
    result = query_api(
        method="POST",
        path="/test/",
        body='{"key": "value"}',
        api_base_url="http://localhost:42002"
    )
    # Should not be a JSON parse error
    assert "Invalid JSON body" not in result
    print(f"✓ Valid JSON body test passed: {result[:80]}...")


def main():
    """Run all tests."""
    print("Testing query_api function...\n")
    
    tests = [
        test_query_api_invalid_method,
        test_query_api_connection_error,
        test_query_api_invalid_json_body,
        test_query_api_valid_body,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1
    
    print(f"\n{passed}/{len(tests)} tests passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
