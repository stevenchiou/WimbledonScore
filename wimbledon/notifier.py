import requests

TELEGRAM_MAX_LENGTH = 4096

HEADER = "\U0001F3BE Wimbledon 賽果更新\n\n"


def _format_line(match: dict) -> str:
    return f"- {match['player1']} vs {match['player2']}: {match['score']}\n"


def build_digest_message(matches: list[dict]) -> list[str]:
    chunks = []
    current = HEADER

    for match in matches:
        line = _format_line(match)
        if len(current) + len(line) > TELEGRAM_MAX_LENGTH:
            chunks.append(current)
            current = HEADER
        current += line

    chunks.append(current)
    return chunks


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    response.raise_for_status()
