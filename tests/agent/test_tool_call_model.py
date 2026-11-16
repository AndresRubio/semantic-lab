import os

import httpx
import pytest

from semantic_lab import config

CUBE_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "cube_query",
        "description": "Send a structured query to the semantic layer and return rows.",
        "parameters": {
            "type": "object",
            "properties": {
                "measures": {"type": "array", "items": {"type": "string"}},
                "dimensions": {"type": "array", "items": {"type": "string"}},
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "member": {"type": "string"},
                            "operator": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "time": {
                    "type": "object",
                    "properties": {
                        "dimension": {"type": "string"},
                        "granularity": {"type": "string"},
                        "date_range": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    },
}


@pytest.mark.model
def test_model_returns_a_well_formed_cube_query_call() -> None:
    # The model loads on first use, which can take a minute or more.
    settings = config.load(os.environ)
    response = httpx.post(
        f"{settings.ollama_url}/api/chat",
        json={
            "model": settings.model,
            "stream": False,
            "options": {"temperature": 0, "seed": 7},
            "messages": [
                {"role": "user", "content": "Revenue by origin country for 2025, by quarter."}
            ],
            "tools": [CUBE_QUERY_TOOL],
        },
        timeout=300.0,
    )
    response.raise_for_status()
    message = response.json()["message"]
    tool_calls = message.get("tool_calls", [])
    assert len(tool_calls) == 1, message
    function = tool_calls[0]["function"]
    assert function["name"] == "cube_query", message
    arguments = function["arguments"]
    assert isinstance(arguments, dict), message
    measures = arguments.get("measures")
    assert isinstance(measures, list) and measures, message
    assert all(isinstance(measure, str) for measure in measures), message
