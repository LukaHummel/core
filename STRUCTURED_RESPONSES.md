# Gemini speech and display responses (experimental fork)

This feature is disabled by default. Reconfigure the Google Gemini **conversation
agent** under Settings → Devices & services and enable **Separate spoken and
display responses**. It is available with recommended model settings as well.
AI tasks, STT and TTS subentries are unchanged.

The normal conversation request still runs Home Assistant tools, search grounding,
and thought-signature handling. Once that request finishes, a separate, tool-free
Gemini request formats its answer into concise plain speech and an optional native
simple card. A simple acknowledgement can have `card: null`. The formatter sees
only the completed answer and response language, and cannot execute commands.
The formatter has a separate 60-second deadline. Live testing found valid
structured generation can exceed the integration's 10-second setup deadline.
This costs an additional API request and adds latency. All speech deltas wait for
formatting; the pipeline receives only the final spoken answer. With the option
disabled, the original streaming behavior is unchanged.

Malformed, incomplete, empty, oversized, rejected or timed-out formatting output
falls back to the original plain answer. No tool request is retried for a
formatting failure. Conversation errors and unfinished tool iterations are not
formatted. The original IntentResponse result metadata, language, conversation ID
and follow-up flag are retained. Chat history keeps the full original answer and
its native thought signatures, so follow-up requests still have the details.

Example `conversation.process` response (other existing response fields omitted):

```json
{
  "response": {
    "speech": {"plain": {"speech": "Here are the cooking steps.", "extra_data": null}},
    "card": {"simple": {"title": "Dinner", "content": "1. Prepare the ingredients.\n2. Cook for 20 minutes."}}
  }
}
```

## Install for testing

This branch starts from current upstream `dev` (2026.11 development Core) and
requires Python 3.14.2 or later. Use a separate test installation/configuration.
It is a Core source patch; installing the View Assist fork alone does not change
Gemini. Do not copy these files into a Core release with different APIs.

On Linux/WSL, with Git and uv installed:

```sh
git clone --branch feature/gemini-intent-response-cards https://github.com/LukaHummel/core.git
cd core
script/setup
source .venv/bin/activate
python3 -m script.translations develop --integration google_generative_ai_conversation
hass -c "$PWD/config"
```

If you already have a configured Core development installation, check out this
branch, refresh its environment, generate translations, and restart that instance.
Configure Google Gemini with your own API key. The API key is never included in
this repository. Keep the default model initially; unsupported structured-output
models will use the documented plain-response fallback.

Install the matching View Assist fork in this test instance as described in its
`NATIVE_RESPONSE_CARDS.md`. Existing Info dashboards need no modification.

## Checks and manual test

```sh
uv run --no-sync pytest -q tests/components/google_generative_ai_conversation
uv run --no-sync prek run --all-files
```

1. With the option off, ask a long question and verify the usual speech stream.
2. Enable it and ask for a recipe or detailed explanation. Call
   `conversation.process` with this agent in Developer tools → Actions and inspect
   the returned `response.speech.plain` and `response.card.simple`. Verify that
   speech is concise, the card has the details, and View Assist opens Info.
3. Ask a follow-up in the same conversation ID. It should retain the full answer.
4. Turn an exposed light on/off and add a shopping-list item. Confirm each action
   happens once and View Assist retains the entity/todo screen priority.
5. Try with prefer-local intents both on and off, and with your microphone/
   satellite pipeline. Confirm speech matches the returned speech and raw JSON
   never reaches TTS. Local matching still happens before this agent is invoked.
6. Formatter failures are covered with mocked API errors, timeout, empty and
   invalid JSON; those cases return the original answer. An error in the primary
   conversation request remains a conversation error.

Disable the option to return to the original Gemini streaming behavior. Revert to
your previous Core checkout to uninstall the patch.

See `PATCH_VALIDATION.md` for the actual checks run for this branch.
