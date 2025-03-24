import pytest
from unittest.mock import Mock, patch
from gptme.llm.llm_anthropic import chat, stream, init
from gptme.message import Message

@pytest.fixture
def mock_anthropic():
    with patch('gptme.llm.llm_anthropic._anthropic') as mock:
        # Initialize with mock API key
        init({"ANTHROPIC_API_KEY": "test_key"})
        yield mock

def test_chat_claude37_thinking_enabled(mock_anthropic):
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Hello"),
    ]
    
    # Mock response with thinking blocks
    mock_response = Mock()
    mock_response.content = [
        {
            "type": "thinking",
            "thinking": "Let me think about how to respond...",
            "signature": "test_signature"
        },
        {
            "type": "text",
            "text": "Hello! How can I help you today?"
        }
    ]
    mock_anthropic.messages.create.return_value = mock_response

    result = chat(messages, "claude-3-7-sonnet", None)
    
    # Verify the API was called with correct parameters
    mock_anthropic.messages.create.assert_called_once()
    call_kwargs = mock_anthropic.messages.create.call_args.kwargs
    assert call_kwargs["thinking"] == {"type": "enabled", "budget_tokens": 16000}
    assert call_kwargs["max_tokens"] == 128000
    assert call_kwargs["headers"] == {"anthropic-beta": "output-128k-2025-02-19"}

def test_chat_claude37_redacted_thinking(mock_anthropic):
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Hello"),
    ]
    
    # Mock response with redacted thinking block
    mock_response = Mock()
    mock_response.content = [
        {
            "type": "redacted_thinking",
            "data": "encrypted_data_here"
        },
        {
            "type": "text",
            "text": "Hello! How can I help you today?"
        }
    ]
    mock_anthropic.messages.create.return_value = mock_response

    result = chat(messages, "claude-3-7-sonnet", None)
    assert "Hello! How can I help you today?" in result

@pytest.mark.asyncio
async def test_stream_claude37_thinking(mock_anthropic):
    messages = [
        Message(role="system", content="You are a helpful assistant"),
        Message(role="user", content="Hello"),
    ]
    
    # Mock streaming response
    mock_stream = Mock()
    mock_stream.__aiter__ = Mock(return_value=iter([
        Mock(type="content_block_start", content_block={"type": "thinking", "thinking": ""}),
        Mock(type="content_block_delta", delta={"type": "thinking_delta", "thinking": "Let me think..."}),
        Mock(type="content_block_delta", delta={"type": "signature_delta", "signature": "test_sig"}),
        Mock(type="content_block_stop"),
        Mock(type="content_block_start", content_block={"type": "text", "text": ""}),
        Mock(type="content_block_delta", delta={"type": "text_delta", "text": "Hello!"}),
        Mock(type="content_block_stop"),
    ]))
    mock_anthropic.messages.stream.return_value.__enter__.return_value = mock_stream

    chunks = []
    async for chunk in stream(messages, "claude-3-7-sonnet", None):
        chunks.append(chunk)
    
    # Verify streaming output contains thinking blocks and text
    assert any("<thinking>" in chunk for chunk in chunks)
    assert any("Let me think..." in chunk for chunk in chunks)
    assert any("</thinking>" in chunk for chunk in chunks)
    assert any("Hello!" in chunk for chunk in chunks)

    # Verify API was called with correct parameters
    mock_anthropic.messages.stream.assert_called_once()
    call_kwargs = mock_anthropic.messages.stream.call_args.kwargs
    assert call_kwargs["thinking"] == {"type": "enabled", "budget_tokens": 16000}
    assert call_kwargs["max_tokens"] == 128000
    assert call_kwargs["headers"] == {"anthropic-beta": "output-128k-2025-02-19"}
