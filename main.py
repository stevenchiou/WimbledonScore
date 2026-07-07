import datetime
import os

import requests

from wimbledon.fetch_matches import fetch_today_matches
from wimbledon.notifier import build_digest_message, send_telegram_message
from wimbledon.state_store import load_state, save_state

DEFAULT_STATE_PATH = "state/wimbledon_state.json"


def run(api_key: str, bot_token: str, chat_id: str, state_path: str = DEFAULT_STATE_PATH) -> None:
    state = load_state(state_path)
    already_notified = set(state["notified_match_ids"])

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")

    try:
        matches = fetch_today_matches(api_key, today)
    except requests.RequestException as exc:
        print(f"Failed to fetch matches: {exc}")
        return

    newly_finished = [
        m for m in matches
        if m["status"] == "finished" and m["match_id"] not in already_notified
    ]

    if not newly_finished:
        return

    chunks = build_digest_message(newly_finished)

    try:
        for chunk in chunks:
            send_telegram_message(bot_token, chat_id, chunk)
    except requests.RequestException as exc:
        print(f"Failed to send Telegram message: {exc}")
        return

    updated_ids = sorted(already_notified | {m["match_id"] for m in newly_finished})
    save_state(state_path, {"notified_match_ids": updated_ids})


if __name__ == "__main__":
    run(
        api_key=os.environ["TENNIS_API_KEY"],
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        chat_id=os.environ["TELEGRAM_CHAT_ID"],
    )
