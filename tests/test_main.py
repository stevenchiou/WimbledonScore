from unittest.mock import patch

from main import run


def make_match(match_id, status):
    return {
        "match_id": match_id,
        "status": status,
        "player1": "A",
        "player2": "B",
        "score": "6-4, 6-2, 6-3",
    }


@patch("main.send_telegram_message")
@patch("main.fetch_today_matches")
def test_run_does_nothing_when_no_finished_matches(mock_fetch, mock_send, tmp_path):
    state_path = str(tmp_path / "state.json")
    mock_fetch.return_value = [make_match("1", "in_progress")]

    run(api_key="k", bot_token="t", chat_id="c", state_path=state_path)

    mock_send.assert_not_called()


@patch("main.save_state")
@patch("main.load_state")
@patch("main.send_telegram_message")
@patch("main.fetch_today_matches")
def test_run_sends_digest_and_updates_state_on_new_finished_match(
    mock_fetch, mock_send, mock_load_state, mock_save_state
):
    mock_load_state.return_value = {"notified_match_ids": []}
    mock_fetch.return_value = [make_match("1", "finished")]

    run(api_key="k", bot_token="t", chat_id="c", state_path="unused.json")

    mock_send.assert_called_once()
    mock_save_state.assert_called_once_with(
        "unused.json", {"notified_match_ids": ["1"]}
    )


@patch("main.save_state")
@patch("main.load_state")
@patch("main.send_telegram_message")
@patch("main.fetch_today_matches")
def test_run_skips_already_notified_matches(
    mock_fetch, mock_send, mock_load_state, mock_save_state
):
    mock_load_state.return_value = {"notified_match_ids": ["1"]}
    mock_fetch.return_value = [make_match("1", "finished")]

    run(api_key="k", bot_token="t", chat_id="c", state_path="unused.json")

    mock_send.assert_not_called()
    mock_save_state.assert_not_called()


@patch("main.save_state")
@patch("main.load_state")
@patch("main.fetch_today_matches")
def test_run_does_not_update_state_when_fetch_fails(
    mock_fetch, mock_load_state, mock_save_state
):
    import requests

    mock_load_state.return_value = {"notified_match_ids": []}
    mock_fetch.side_effect = requests.RequestException("boom")

    run(api_key="k", bot_token="t", chat_id="c", state_path="unused.json")

    mock_save_state.assert_not_called()


@patch("main.save_state")
@patch("main.load_state")
@patch("main.send_telegram_message")
@patch("main.fetch_today_matches")
def test_run_does_not_update_state_when_send_fails(
    mock_fetch, mock_send, mock_load_state, mock_save_state
):
    import requests

    mock_load_state.return_value = {"notified_match_ids": []}
    mock_fetch.return_value = [make_match("1", "finished")]
    mock_send.side_effect = requests.RequestException("boom")

    run(api_key="k", bot_token="t", chat_id="c", state_path="unused.json")

    mock_save_state.assert_not_called()
