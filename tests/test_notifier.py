from wimbledon.notifier import build_digest_message, TELEGRAM_MAX_LENGTH


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
