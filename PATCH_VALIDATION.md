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

## Paired and live E2E testing

After the initial component checks, 10 paired application E2E scenarios passed
through authenticated HTTP, the real Gemini SDK against a loopback HTTP/SSE
provider, HA state events and the actual View Assist navigation manager. These
cover cards, ordinary streaming requests, follow-up history, repeat speech,
timed revert, command priority and error fallbacks.

Live Docker testing found valid structured generation took about 29 seconds,
longer than the initial 10-second formatter deadline. The formatter now has its
own 60-second deadline and explicitly disables SDK automatic function calling.
All 24 response tests and 10 paired E2E cases passed again after this fix. Scoped
lint, formatting, Pylint and mypy checks passed on the revised code.

A live spoken recipe passed through Gemini STT, conversation, structured
formatting, real View Assist sensor/navigation/browser rendering and Gemini TTS
in 71.4 seconds. The actual Info screen and generated audio were captured. A
spoken light command then changed a virtual light exactly once and opened the
actual intent view in 12.2 seconds. The live todo attempt was blocked by the
Gemini 2.5 Flash daily free-tier quota; it is not claimed to pass.

Synthetic recorded audio was uploaded through the Assist WebSocket protocol. A
test bridge forwarded the complete pipeline intent result into the configured
intent sensor. This does not verify a physical microphone, satellite wiring or
speaker playback. The recipe used Gemini 2.5 Flash STT, Gemini 3.1 Flash Lite
conversation/formatting and Gemini 3.1 Flash TTS Preview. The light command used
Gemini 2.5 Flash conversation after high-demand errors from the default model.

Provider 503 errors, synthetic-name misrecognition, an empty primary response
and quota failures are retained in the local HTML report alongside final results.
The matching View Assist fork has 23 callback regression tests. No credentials
or authentication tokens are included in the report or committed sources.