# tests/test_fetch_matches.py
import json
from pathlib import Path

import responses

from wimbledon.fetch_matches import normalize_match, fetch_today_matches

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_normalize_match_maps_not_started_singles_match():
    raw = load_fixture("list_by_date_sample.json")
    event = raw["Stages"][0]["Events"][0]

    result = normalize_match(event)

    assert result == {
        "match_id": "1818982",
        "status": "not_started",
        "player1": "Jannik Sinner",
        "player2": "Jan-Lennard Struff",
        "score": "",
    }


def test_normalize_match_maps_finished_match_with_score():
    raw = load_fixture("list_by_date_sample.json")
    event = raw["Stages"][0]["Events"][1]

    result = normalize_match(event)

    assert result == {
        "match_id": "1808175",
        "status": "finished",
        "player1": "Jannik Sinner",
        "player2": "Nuno Borges",
        "score": "7-6, 7-6, 6-4",
    }


def test_normalize_match_maps_in_progress_match():
    """Test that set-in-progress codes (S1-S5) map to 'in_progress' status."""
    event = {
        "Eid": "9999999",
        "T1": [{"ID": "123", "Nm": "Player One", "Abr": "P1"}],
        "T2": [{"ID": "456", "Nm": "Player Two", "Abr": "P2"}],
        "Eps": "S2",
    }

    result = normalize_match(event)

    assert result == {
        "match_id": "9999999",
        "status": "in_progress",
        "player1": "Player One",
        "player2": "Player Two",
        "score": "",
    }


@responses.activate
def test_fetch_today_matches_returns_only_wimbledon_stages():
    raw = load_fixture("list_by_date_sample.json")
    responses.add(
        responses.GET,
        "https://livescore6.p.rapidapi.com/matches/v2/list-by-date",
        json=raw,
        status=200,
    )

    result = fetch_today_matches(api_key="fake-key", date="20260707")

    assert len(result) == 3
    match_ids = {m["match_id"] for m in result}
    assert match_ids == {"1818982", "1808175", "1818987"}
    assert "1818821" not in match_ids
