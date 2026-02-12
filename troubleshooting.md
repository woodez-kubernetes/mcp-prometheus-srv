# Troubleshooting Log

## Issue 1: All mocked httpx tests failing with JSONDecodeError

**When:** Stage 2 — initial test run

**Symptom:** 16 of 18 tests failed with `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`. Only the `health()` tests passed (because they don't call `.json()` on the response).

**Root cause:** The `_mock_response()` helper was constructing `httpx.Response` with a `json=json_data` keyword argument. However, `httpx.Response.__init__` does **not** accept a `json` parameter to set the body — that kwarg is silently ignored. The response's `.content` remained empty bytes, so when `_get()` called `resp.json()`, it tried to parse an empty string and raised `JSONDecodeError`.

**Why this happened:** The `httpx.Response` constructor accepts `content` (bytes), `text` (str), `html` (str), or `stream`, but **not** `json`. This differs from libraries like `requests-mock` or `aioresponses` where you can pass `json=` directly.

**Fix:** Changed `_mock_response()` to serialize the JSON data into bytes and pass it via the `content` parameter:

```python
# Before (broken):
resp = httpx.Response(status_code=..., json=json_data, ...)

# After (working):
content = json.dumps(json_data).encode() if json_data else text.encode()
resp = httpx.Response(status_code=..., content=content, ...)
```

**Result:** All 18 tests pass.
