"""Tests for separate speech and card responses."""

import json
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientConnectionError
from google.genai.types import GenerateContentResponse
from httpx2 import ConnectError
import pytest

from homeassistant.components import conversation
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_STRUCTURED_RESPONSE,
    DOMAIN,
)
from homeassistant.components.google_generative_ai_conversation.response import (
    parse_response,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent, llm
from homeassistant.helpers.chat_session import async_get_chat_session
from homeassistant.setup import async_setup_component

from . import API_ERROR_500

from tests.common import MockConfigEntry
from tests.components.conversation import (
    MockChatLog,
    mock_chat_log,  # noqa: F401
)

ANSWER = "Here is a detailed answer with several useful facts."
CARD = {"title": "Details", "content": ANSWER}


def text_response(text: str) -> GenerateContentResponse:
    """Make a Gemini text response."""
    return GenerateContentResponse(
        candidates=[{"content": {"role": "model", "parts": [{"text": text}]}}]
    )


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "not JSON",
        "[]",
        '{"speech": "Hello"}',
        '{"speech": " ", "card": null}',
        '{"speech": 3, "card": null}',
        '{"speech": "Hello", "card": {"title": "x", "content": []}}',
        '{"speech": "Hello", "card": {"title": "x", "content": " "}}',
        '{"speech": "Hello", "card": null, "tool_calls": []}',
        json.dumps({"speech": "x" * 2001, "card": None}),
    ],
)
def test_invalid_response(text: str | None) -> None:
    """Reject incomplete, malformed, or unsafe model output."""
    with pytest.raises(ValueError):
        parse_response(text)


@pytest.mark.parametrize("card", [None, CARD])
def test_valid_response(card: dict[str, str] | None) -> None:
    """Accept concise speech with an optional native card."""
    assert parse_response(json.dumps({"speech": "Résumé", "card": card})) == (
        "Résumé",
        card,
    )


async def test_structured_conversation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_send_message_stream: AsyncMock,
    mock_generate_content: AsyncMock,
    mock_chat_create: Mock,
) -> None:
    """Keep the normal request plain and expose only final speech to the pipeline."""
    subentry = mock_config_entry.subentries["ulid-conversation"]
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_STRUCTURED_RESPONSE: True},
    )
    with patch("google.genai.models.AsyncModels.get"):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    mock_send_message_stream.return_value = [[text_response(ANSWER)]]
    mock_generate_content.return_value = text_response(
        json.dumps({"speech": "Here are the details.", "card": CARD})
    )
    listener = Mock()
    with (
        async_get_chat_session(hass, None) as session,
        conversation.async_get_chat_log(
            hass, session, chat_log_delta_listener=listener
        ) as chat_log,
    ):
        result = await conversation.async_converse(
            hass,
            "Explain this",
            session.conversation_id,
            Context(),
            agent_id="conversation.google_ai_conversation",
        )
        assert chat_log.delta_listener is listener

    expected_speech = "Here are the details."
    assert result.response.speech["plain"]["speech"] == expected_speech
    assert result.response.card == {"simple": CARD}
    assert result.conversation_id == session.conversation_id
    assert mock_chat_create.call_args.kwargs["config"].response_mime_type is None
    config = mock_generate_content.call_args.kwargs["config"]
    assert config.tools is None
    assert config.automatic_function_calling.disable is True
    assert config.response_mime_type == "application/json"
    assert listener.call_args.args[1]["content"] == expected_speech
    assert len([c for c in listener.call_args_list if c.args[1].get("content")]) == 1


@pytest.mark.parametrize(
    "formatted",
    [
        text_response("not JSON"),
        text_response('{"speech": "short", "card": {"content": "bad"}}'),
        GenerateContentResponse(),
        API_ERROR_500,
        TimeoutError(),
        ClientConnectionError("connection unavailable"),
        ConnectError("connection unavailable"),
    ],
)
async def test_format_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_send_message_stream: AsyncMock,
    mock_generate_content: AsyncMock,
    formatted: GenerateContentResponse | Exception,
) -> None:
    """A formatter failure preserves the original answer and never reruns commands."""
    subentry = mock_config_entry.subentries["ulid-conversation"]
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_STRUCTURED_RESPONSE: True},
    )
    with patch("google.genai.models.AsyncModels.get"):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    mock_send_message_stream.return_value = [[text_response(ANSWER)]]
    mock_generate_content.side_effect = [formatted]
    result = await conversation.async_converse(
        hass,
        "Explain this",
        None,
        Context(),
        agent_id="conversation.google_ai_conversation",
    )
    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == ANSWER
    assert result.response.card == {}
    assert mock_send_message_stream.call_count == 1
    assert mock_generate_content.call_count == 1


async def test_structured_tool_result(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
    mock_send_message_stream: AsyncMock,
    mock_generate_content: AsyncMock,
    mock_chat_create: Mock,
) -> None:
    """Execute a tool once and retain its native success metadata after formatting."""
    subentry = mock_config_entry.subentries["ulid-conversation"]
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_STRUCTURED_RESPONSE: True},
    )
    with patch("google.genai.models.AsyncModels.get"):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    original = intent.IntentResponse(language="en")
    target = intent.IntentResponseTarget(
        name="Kitchen", type=intent.IntentResponseTargetType.ENTITY, id="light.kitchen"
    )
    original.async_set_results([target])
    mock_chat_log.mock_tool_results({"test-call": llm.IntentResponseDict(original)})
    mock_send_message_stream.return_value = [
        [
            GenerateContentResponse(
                candidates=[
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "function_call": {
                                        "name": "HassTurnOn",
                                        "args": {"name": "Kitchen"},
                                    }
                                }
                            ],
                        }
                    }
                ]
            )
        ],
        [text_response("Turned on the kitchen light.")],
    ]
    mock_generate_content.return_value = text_response(
        '{"speech": "Done.", "card": null}'
    )
    with patch("homeassistant.helpers.llm.ulid_now", return_value="test-call"):
        result = await conversation.async_converse(
            hass,
            "Turn on the kitchen light",
            mock_chat_log.conversation_id,
            Context(),
            agent_id="conversation.google_ai_conversation",
        )
    assert result.response is original
    assert result.response.success_results == [target]
    assert result.response.speech["plain"]["speech"] == "Done."
    assert mock_send_message_stream.call_count == 2
    assert mock_generate_content.call_count == 1
    assert mock_chat_create.call_args.kwargs["config"].tools
    assert mock_generate_content.call_args.kwargs["config"].tools is None
    assert (
        mock_send_message_stream.call_args.kwargs["message"][0].function_response.name
        == "HassTurnOn"
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_disabled_keeps_streaming(
    hass: HomeAssistant,
    mock_send_message_stream: AsyncMock,
    mock_generate_content: AsyncMock,
) -> None:
    """The default agent still forwards ordinary streaming deltas without formatting."""
    mock_send_message_stream.return_value = [
        [text_response("Hello "), text_response("world")]
    ]
    listener = Mock()
    with (
        async_get_chat_session(hass, None) as session,
        conversation.async_get_chat_log(
            hass, session, chat_log_delta_listener=listener
        ),
    ):
        result = await conversation.async_converse(
            hass,
            "Hello",
            session.conversation_id,
            Context(),
            agent_id="conversation.google_ai_conversation",
        )
    assert result.response.speech["plain"]["speech"] == "Hello world"
    assert [
        c.args[1]["content"]
        for c in listener.call_args_list
        if c.args[1].get("content")
    ] == ["Hello ", "world"]
    mock_generate_content.assert_not_called()


async def test_primary_error_restores_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_generate_content: AsyncMock,
    mock_send_message_stream: AsyncMock,
) -> None:
    """Primary errors remain conversation errors; formatting never runs."""
    subentry = mock_config_entry.subentries["ulid-conversation"]
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_STRUCTURED_RESPONSE: True},
    )
    with patch("google.genai.models.AsyncModels.get"):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    mock_send_message_stream.side_effect = API_ERROR_500
    listener = Mock()
    with (
        async_get_chat_session(hass, None) as session,
        conversation.async_get_chat_log(
            hass, session, chat_log_delta_listener=listener
        ) as chat_log,
    ):
        result = await conversation.async_converse(
            hass,
            "Hello",
            session.conversation_id,
            Context(),
            agent_id="conversation.google_ai_conversation",
        )
        assert chat_log.delta_listener is listener
    assert result.response.response_type is intent.IntentResponseType.ERROR
    mock_generate_content.assert_not_called()
