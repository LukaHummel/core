# Patch validation

Validated on 12 October 2026 against upstream `dev` at
`9942caba481e51760915abb788620bf25e492104`, using Linux Python 3.14.8
(the repository pins 3.14.5; its minimum is 3.14.2).

## Automated coverage

- The integration regression run passed 284 tests, including the initial 22
  structured-response tests, before an existing TTS test failed because the
  test environment lacked `ffmpeg`.
- After unpacking Ubuntu's ffmpeg and its dependencies locally, all 11 tests in
  `test_tts.py` passed.
- The final `test_response.py` run, including additional aiohttp and httpx2
  connection-error fallbacks: 24 passed.
- Ruff lint and formatting on changed Python files, Pylint on changed production
  files and the new tests, and targeted mypy on `conversation.py`/`response.py`:
  passed.
- Changed-file repository hooks (pinned Ruff, codespell, JSON and Prettier): passed.
  Mypy, Pylint and hassfest were run separately with the scope reported above.
- Integration-scoped `script.hassfest`: 1 integration, 0 invalid integrations.
- English translations generated; Python 3.14 compilation and whitespace checks
  passed.

The new tests exercise the actual conversation agent and chat log, including
one-time Home Assistant tool execution, preservation of native success metadata,
plain primary requests, tool-free formatting, buffered final speech, unchanged
streaming when disabled, restored listeners after primary errors, and API,
transport, timeout, malformed, empty and oversized response fallbacks.

## Environment limitations

`script/setup` was attempted but installation of all unrelated integration
requirements failed while resolving the build dependencies of `pyatome==0.1.2`
(`idna==3.20` lacked expected wheel metadata). A targeted environment using the
repository's runtime/test requirements and this integration's dependencies was
used instead.

`uv run --no-sync prek run --all-files` was attempted on an identical Linux copy
of the staged patch. It was stopped during the all-repository Pylint scan of
19,175 files after approximately 14 minutes. The complete all-repository hook
suite is not claimed to pass. Targeted checks are reported above.

No real Gemini credentials, microphone/satellite or dashboard was used. Run the
manual checks in `STRUCTURED_RESPONSES.md` on your test instance before using this
experimental branch in your regular installation. The matching View Assist
fork has its own `PATCH_VALIDATION.md` and 23 callback/routing tests.
