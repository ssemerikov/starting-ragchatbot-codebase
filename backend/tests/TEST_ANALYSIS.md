# Test Analysis: RAG Chatbot Query Failures

## Executive Summary

The RAG chatbot is returning "query failed" for all content-related questions due to **SSL/TLS certificate verification failures** when connecting to the OpenRouter API. All components of the system (CourseSearchTool, vector store, tool manager) are working correctly - the issue is isolated to the API communication layer.

## Test Results

### ✅ PASSING: CourseSearchTool (6/6 tests)
- `test_tool_definition` - Tool definition format is correct
- `test_simple_search` - Search functionality works (returns 3025 chars of relevant content)
- `test_search_with_course_filter` - Course filtering works
- `test_search_with_lesson_filter` - Lesson filtering works
- `test_search_no_results` - Handles empty results properly
- `test_source_tracking` - Source tracking for UI works

**Verdict**: ✅ CourseSearchTool.execute() is functioning perfectly

### ✅ PASSING: RAG System Components (3/3 tests)
- `test_rag_system_initialization` - All components initialize correctly
- `test_tool_registration` - Both tools (search_course_content, get_course_outline) are registered
- `test_course_analytics` - Vector store has 4 courses with 528 chunks loaded

**Verdict**: ✅ RAG system integration is correct

### ❌ FAILING: AI Generator API Calls (2/2 tests)
- `test_simple_content_query` - Fails with SSL certificate error
- `test_simple_api_call` - Fails with same SSL error

**Error Message**:
```
Error: All models failed. Last error with qwen/qwen-2.5-72b-instruct:free:
upstream connect error or disconnect/reset before headers.
reset reason: remote connection failure,
transport failure reason: TLS_error:|268435581:SSL routines:OPENSSL_internal:CERTIFICATE_VERIFY_FAILED:TLS_error_end
```

### 🔍 ROOT CAUSE IDENTIFIED

**Network/DNS Issue**: The environment cannot resolve `openrouter.ai`
- Test shows: `[Errno -3] Temporary failure in name resolution`
- This suggests the environment has network restrictions or is behind a proxy

**SSL Certificate Verification**: Even when DNS resolves (through upstream proxy), SSL certificate chain validation fails
- Error code: `TLS_error:|268435581:SSL routines:OPENSSL_internal:CERTIFICATE_VERIFY_FAILED`
- This prevents ALL API calls from succeeding

## Impact Analysis

### What Works
1. ✅ Vector store search
2. ✅ Course data retrieval
3. ✅ Tool execution (when called directly)
4. ✅ Session management
5. ✅ Course analytics
6. ✅ Tool registration

### What Fails
1. ❌ **Any query requiring AI response**
2. ❌ All OpenRouter API calls
3. ❌ All fallback models (they all fail with the same SSL error)

### User Impact
- Users see "query failed" for ANY question
- The chatbot is completely non-functional for end users
- No AI-generated responses can be produced

## Proposed Fixes

### Fix Option 1: Configure SSL Verification (Quick Fix)
**Modify `backend/ai_generator.py` to handle SSL configuration**

```python
# In AIGenerator.__init__
import httpx

# Create custom HTTP client with SSL configuration
http_client = httpx.Client(
    verify=False  # Disable SSL verification (NOT RECOMMENDED for production)
)

self.client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    http_client=http_client
)
```

**Pros**:
- Quick fix
- Will work immediately

**Cons**:
- **SECURITY RISK**: Disables SSL verification
- Not suitable for production
- Opens up to man-in-the-middle attacks

### Fix Option 2: Use Environment CA Certificates (Recommended)
**Update `backend/ai_generator.py` to use system certificates**

```python
import httpx
import ssl
import certifi

# Create SSL context with system certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())

# Create HTTP client with proper SSL configuration
http_client = httpx.Client(
    verify=ssl_context
)

self.client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    http_client=http_client
)
```

**Requirements**: Install certifi
```bash
uv add certifi
```

**Pros**:
- Maintains security
- Uses trusted certificate chain
- Production-ready

**Cons**:
- Requires additional dependency

### Fix Option 3: Network Configuration (System-level)
**Fix DNS/network access to openrouter.ai**

This requires:
1. Configure DNS resolution for `openrouter.ai`
2. Ensure firewall allows HTTPS traffic to OpenRouter
3. Configure proxy settings if behind corporate proxy

**Pros**:
- Addresses root cause
- No code changes needed

**Cons**:
- Requires system/network admin access
- May not be possible in restricted environments

### Fix Option 4: Retry with Better Error Handling (Defensive)
**Add retry logic and better error messages**

```python
# In AIGenerator.generate_response()
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def _make_api_call(self, api_params):
    return self.client.chat.completions.create(**api_params)
```

Add user-friendly error messages:
```python
if "CERTIFICATE_VERIFY_FAILED" in error_msg:
    return "I'm experiencing connectivity issues. Please check your network settings or contact support."
```

**Pros**:
- Better user experience
- Handles transient network issues

**Cons**:
- Doesn't fix the root SSL problem
- Still fails but with better messaging

## Recommended Implementation Plan

### Phase 1: Immediate Fix (Option 2 - Certifi)
1. Add certifi dependency
2. Update AIGenerator to use certifi certificates
3. Test with diagnostic tests
4. Verify queries work

### Phase 2: Enhanced Error Handling (Option 4)
1. Add retry logic for transient errors
2. Add user-friendly error messages
3. Log API errors for debugging

### Phase 3: Network Investigation (Option 3)
1. Investigate network restrictions
2. Configure DNS/proxy if needed
3. Document network requirements

## Testing Commands

Run these commands to verify fixes:

```bash
# Run diagnostic tests
uv run python -m pytest tests/test_diagnostics.py -v -s

# Run CourseSearchTool tests (should all pass)
uv run python -m pytest tests/test_course_search_tool.py -v

# Run RAG system tests (critical test)
uv run python -m pytest tests/test_rag_system.py::TestRAGSystemQueries::test_simple_content_query -v -s

# Run all tests
uv run python -m pytest tests/ -v
```

## Conclusion

The RAG chatbot's core functionality is **100% working**. The failure is entirely due to **network/SSL issues** preventing API communication with OpenRouter. Implementing Fix Option 2 (certifi certificates) will likely resolve the issue while maintaining security.
