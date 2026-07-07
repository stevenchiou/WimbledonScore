# wimbledon/fetch_matches.py
import requests

API_HOST = "livescore6.p.rapidapi.com"
MATCHES_URL = f"https://{API_HOST}/matches/v2/list-by-date"

STATUS_MAP = {
    "NS": "not_started",
    "FT": "finished",
    "Ret.": "finished",
    "W.O.": "finished",
    "S1": "in_progress",
    "S2": "in_progress",
    "S3": "in_progress",
    "S4": "in_progress",
    "S5": "in_progress",
}

SET_KEYS = [f"S{i}" for i in range(1, 6)]


def _team_name(team: list) -> str:
    return " / ".join(player["Nm"] for player in team)


def _format_score(raw: dict) -> str:
    sets = []
    for set_key in SET_KEYS:
        t1_key = f"Tr1{set_key}"
        t2_key = f"Tr2{set_key}"
        if t1_key in raw and t2_key in raw:
            sets.append(f"{raw[t1_key]}-{raw[t2_key]}")
    return ", ".join(sets)


def normalize_match(raw: dict) -> dict:
    return {
        "match_id": str(raw["Eid"]),
        "status": STATUS_MAP.get(raw.get("Eps"), "not_started"),
        "player1": _team_name(raw["T1"]),
        "player2": _team_name(raw["T2"]),
        "score": _format_score(raw),
    }


def fetch_today_matches(api_key: str, date: str) -> list[dict]:
    response = requests.get(
        MATCHES_URL,
        headers={
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": API_HOST,
        },
        params={"Category": "tennis", "Date": date},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    matches = []
    for stage in data.get("Stages", []):
        if stage.get("Cnm") != "Wimbledon":
            continue
        for event in stage.get("Events", []):
            matches.append(normalize_match(event))
    return matches
