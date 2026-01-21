# history-compression Proposal

## Why

When sessions are removed from the 5-session rolling window (Sprint 3), the historical context is lost. AI-powered compression preserves the narrative meaning ("Implemented auth flow, hit a blocker with OAuth, pivoted to JWT") in a token-efficient format for the Brain Reboot feature (Sprint 5).

## What Changes

- **Rolling Window Integration**: Hook into Sprint 3's FIFO removal to queue sessions for compression
- **Pending Compression Queue**: Store removed sessions in project YAML awaiting AI processing
- **Background Compression Process**: Periodic async processing of pending queue via OpenRouter
- **History Schema**: Add `history` section with `summary` and `last_compressed_at` fields
- **OpenRouter Integration**: HTTP client with authentication, error handling, retry logic
- **AI Summarisation**: Token-efficient prompt design for narrative compression
- **Configuration**: OpenRouter API key, model selection, compression interval in config.yaml

## Impact

- Affected specs: session-summarisation (extends Sprint 3)
- Affected code: `monitor.py` (new history compression functions, background task)
- Affected config: `config.yaml` (new `openrouter` section)
- Dependencies: `requests` library for HTTP calls

## Risk Assessment

- **Risk Level**: Medium
- **Breaking Changes**: None
- **Dependencies**: Requires OpenRouter API key for AI features
- **Fallback**: Sessions queue for compression indefinitely if API unavailable
- **Security**: API key must never appear in logs or responses
