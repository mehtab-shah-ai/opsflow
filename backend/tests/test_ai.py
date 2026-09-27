import httpx
import pytest
from pydantic import ValidationError

from app.ai import Plan, ProviderRouter, build_context


def test_plan_rejects_arbitrary_execution():
    with pytest.raises(ValidationError):
        Plan.model_validate({"tool": "execute_python", "code": "import os"})
    with pytest.raises(ValidationError):
        Plan.model_validate({"tool": "get_dataset_summary", "code": "bad"})


async def test_429_skips_same_provider_keys_and_falls_back():
    calls = []

    def handler(request):
        calls.append(request.url.host)
        if "groq" in request.url.host:
            return httpx.Response(429, json={"error": "quota"})
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": '{"tool":"get_issues"}'}]}}]}
        )

    router = ProviderRouter(
        config={"groq": (["a", "b"], "test-groq"), "gemini": (["c"], "test-gemini")},
        transport=httpx.MockTransport(handler),
    )
    result = await router.generate("test", Plan)
    assert result["value"]["tool"] == "get_issues"
    assert calls == ["api.groq.com", "generativelanguage.googleapis.com"]
    assert router.health()["groq"]["failure"] == "rate_limited"


async def test_malformed_json_falls_back_and_no_keys_is_safe():
    router = ProviderRouter(
        config={"groq": (["a"], "test"), "gemini": ([], "test")},
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
        ),
    )
    assert await router.generate("test", Plan) is None
    empty = ProviderRouter(config={"groq": ([], "test"), "gemini": ([], "test")})
    assert await empty.generate("test", Plan) is None


def test_context_excludes_raw_pii():
    context = build_context(
        {
            "id": "d",
            "fingerprint": "x",
            "analysis": {
                "rows": 1,
                "quality_score": 50,
                "severity": {},
                "categories": {},
                "schema": [{"name": "employee_name", "type": "text"}],
                "operations": {"available": False, "sites": []},
            },
            "data": [{"employee_name": "Secret Person"}],
        }
    )
    assert "Secret Person" not in str(context)
