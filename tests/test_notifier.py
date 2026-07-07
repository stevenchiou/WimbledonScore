import pytest
import responses

from wimbledon.notifier import build_digest_message, TELEGRAM_MAX_LENGTH, send_telegram_message


def make_match(i):
    return {
        "match_id": str(i),
        "status": "finished",
        "player1": f"Player{i}A",
        "player2": f"Player{i}B",
        "score": "6-4, 6-2, 6-3",
    }


def test_build_digest_message_single_match():
    chunks = build_digest_message([make_match(1)])

    assert len(chunks) == 1
    assert "Player1A" in chunks[0]
    assert "Player1B" in chunks[0]
    assert "6-4, 6-2, 6-3" in chunks[0]


def test_build_digest_message_multiple_matches_in_one_chunk():
    matches = [make_match(i) for i in range(5)]

    chunks = build_digest_message(matches)

    assert len(chunks) == 1
    for i in range(5):
        assert f"Player{i}A" in chunks[0]


def test_build_digest_message_splits_into_multiple_chunks_when_too_long():
    matches = [make_match(i) for i in range(400)]

    chunks = build_digest_message(matches)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_LENGTH

    combined = "".join(chunks)
    for i in range(400):
        assert f"Player{i}A" in combined


@responses.activate
def test_send_telegram_message_posts_to_bot_api():
    responses.add(
        responses.POST,
        "https://api.telegram.org/botFAKE_TOKEN/sendMessage",
        json={"ok": True},
        status=200,
    )

    send_telegram_message("FAKE_TOKEN", "12345", "hello")

    assert len(responses.calls) == 1
    sent_body = responses.calls[0].request.body
    assert b"hello" in sent_body
    assert b"12345" in sent_body


@responses.activate
def test_send_telegram_message_raises_on_http_error():
    responses.add(
        responses.POST,
        "https://api.telegram.org/botFAKE_TOKEN/sendMessage",
        json={"ok": False, "description": "bad request"},
        status=400,
    )

    with pytest.raises(Exception):
        send_telegram_message("FAKE_TOKEN", "12345", "hello")
