# tests/test_state_store.py
import json

from wimbledon.state_store import load_state, save_state


def test_load_state_returns_empty_list_when_file_missing(tmp_path):
    path = tmp_path / "state.json"

    state = load_state(str(path))

    assert state == {"notified_match_ids": []}


def test_load_state_reads_existing_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"notified_match_ids": ["m1", "m2"]}))

    state = load_state(str(path))

    assert state == {"notified_match_ids": ["m1", "m2"]}


def test_save_state_writes_json(tmp_path):
    path = tmp_path / "state.json"

    save_state(str(path), {"notified_match_ids": ["m1"]})

    assert json.loads(path.read_text()) == {"notified_match_ids": ["m1"]}


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "state.json"

    save_state(str(path), {"notified_match_ids": ["m1", "m2"]})
    state = load_state(str(path))

    assert state == {"notified_match_ids": ["m1", "m2"]}
