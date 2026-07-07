# Wimbledon Telegram Notifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python service that runs hourly via GitHub Actions, detects Wimbledon matches that have just finished, and sends a Telegram digest with the results.

**Architecture:** A stateless-between-runs script (`main.py`) orchestrates three modules — `fetch_matches` (calls the tennis API and normalizes results), `state_store` (reads/writes a JSON file tracking which matches were already notified), and `notifier` (builds a digest message and sends it via the Telegram Bot API). GitHub Actions runs the script hourly, and the workflow commits the updated state file back to the repo after each run.

**Tech Stack:** Python 3.12, `requests`, `pytest`, GitHub Actions.

## Global Constraints

- Naming: any English word referring to the tournament is spelled `Wimbledon` (exact capitalization) everywhere — file names, identifiers, strings, comments.
- No persistent server or database — GitHub Actions + a JSON file committed to the repo is the only infrastructure.
- Only notify on matches transitioning to `finished` status. Do not notify on match start or in-progress score changes.
- Multiple matches finishing between two runs must be combined into a single digest message (or the minimum number of messages needed to stay under Telegram's 4096-character limit per message), never one message per match.
- A match must only be added to the "already notified" state after the Telegram send for its digest chunk has succeeded. Never mark a match notified before the send that reports it has succeeded.
- On any error calling the tennis API or the Telegram API, log the error and end the run without modifying the state file — the next hourly run retries naturally.
- A day with no Wimbledon matches (off-season or rest day) is not an error; the run ends normally.
- Player names in the Telegram digest are abbreviated to "first initial. surname" (e.g. `"Novak Djokovic"` → `"N. Djokovic"`, `"Carlos Alcaraz"` → `"C. Alcaraz"`), by splitting on the first space and keeping everything after it as the surname portion. Names with no space (a single word) are left unabbreviated. This applies only to the digest message text — the internal `player1`/`player2` fields stay as full names.

---

## File Structure

```
wimbledonscore/
  main.py                          # orchestration entrypoint
  wimbledon/
    __init__.py
    fetch_matches.py                # calls tennis API, normalizes response
    state_store.py                  # load/save state/wimbledon_state.json
    notifier.py                     # build digest text, send via Telegram
  state/
    wimbledon_state.json             # {"notified_match_ids": []}
  tests/
    fixtures/
      raw_sample_response.json       # real captured API response (Task 1)
    test_fetch_matches.py
    test_state_store.py
    test_notifier.py
    test_main.py
  requirements.txt
  .github/workflows/wimbledon-notify.yml
```

## Internal Data Contract

Every task after Task 1 consumes matches in this normalized shape (a plain `dict`), regardless of what the upstream API calls its fields:

```python
{
    "match_id": str,     # stable unique id for the match
    "status": str,       # one of: "not_started", "in_progress", "finished"
    "player1": str,
    "player2": str,
    "score": str,        # human-readable score, e.g. "6-4, 6-2, 6-3"
}
```

---

### Task 1: Research the tennis API and implement `fetch_matches.py`

No public tennis live-score API documentation shows a full example JSON response without an API key — the real field names are unknown until you actually sign up and call it. This task's first half is a research spike; its second half implements and tests the module against what you find. Do not skip ahead to Task 2 until this task's tests pass against a real captured response.

**Files:**
- Create: `wimbledon/__init__.py` (empty file)
- Create: `wimbledon/fetch_matches.py`
- Create: `tests/fixtures/raw_sample_response.json`
- Test: `tests/test_fetch_matches.py`

**Interfaces:**
- Produces: `normalize_match(raw: dict) -> dict` returning the Internal Data Contract shape above
- Produces: `fetch_today_matches(api_key: str) -> list[dict]`, returning a list of normalized match dicts for today's Wimbledon matches

- [ ] **Step 1: Sign up for a tennis API and capture a real response**

  1. Go to https://rapidapi.com and create a free account.
  2. Search the RapidAPI catalog for "tennis" and subscribe to a **free** plan on one of: "Tennis API" (fluis.lacasse / `tennisapi1`), "Tennis Live Data" (sportcontentapi), or "Tennis API - ATP WTA ITF". If the first one you try has no free plan or no Wimbledon/Grand Slam data on the free tier, try the next.
  3. From the API's RapidAPI playground (or via `curl`), call whichever endpoint returns **today's matches** or **live matches** including Wimbledon. Example shape of the call (adjust host/path to the API you subscribed to):
     ```bash
     curl -s "https://<api-host>.p.rapidapi.com/<endpoint-path>" \
       -H "X-RapidAPI-Key: <your-key>" \
       -H "X-RapidAPI-Host: <api-host>.p.rapidapi.com"
     ```
  4. Save the raw JSON response exactly as returned to `tests/fixtures/raw_sample_response.json`.
  5. If today's response has no finished matches (e.g. you're doing this outside the tournament), also fetch and save a **second** fixture, `tests/fixtures/raw_sample_response_historical.json`, by calling the API's historical/results endpoint for a past Wimbledon date, so you have at least one real `finished` match to test against. If the API has no historical endpoint on the free tier, manually take the raw sample and edit a copy so one match's status field is set to whatever raw value you determined means "finished" in Step 2 below — keep this edited copy as `tests/fixtures/raw_sample_response_historical.json` and note in a comment at the top of the test file that it was hand-edited from a real sample for the finished-match case.

- [ ] **Step 2: Identify the real field names**

  Open the saved fixture and identify:
  - Which key is the unique match identifier
  - Which key holds match status, and what the literal values are for "not started", "in progress", and "finished" (tennis APIs commonly use numeric codes or short strings like `"notstarted"`, `"inprogress"`, `"finished"` — read whatever this specific API actually returns)
  - Which keys hold the two players'/teams' names
  - Which key (or nested structure) holds the score

- [ ] **Step 3: Write the failing tests**

  ```python
  # tests/test_fetch_matches.py
  import json
  from pathlib import Path

  import pytest
  import responses

  from wimbledon.fetch_matches import normalize_match, fetch_today_matches

  FIXTURES = Path(__file__).parent / "fixtures"


  def load_fixture(name):
      return json.loads((FIXTURES / name).read_text())


  def test_normalize_match_returns_internal_contract_shape():
      raw = load_fixture("raw_sample_response.json")
      first_match = raw["<list-key-you-found>"][0]  # replace with the real key path

      result = normalize_match(first_match)

      assert set(result.keys()) == {"match_id", "status", "player1", "player2", "score"}
      assert isinstance(result["match_id"], str)
      assert result["status"] in {"not_started", "in_progress", "finished"}


  def test_normalize_match_maps_finished_status():
      raw = load_fixture("raw_sample_response_historical.json")
      finished_raw_match = raw["<list-key-you-found>"][0]  # pick one you know is finished

      result = normalize_match(finished_raw_match)

      assert result["status"] == "finished"
      assert result["player1"]
      assert result["player2"]
      assert result["score"]


  @responses.activate
  def test_fetch_today_matches_calls_api_and_normalizes():
      raw = load_fixture("raw_sample_response.json")
      responses.add(
          responses.GET,
          "https://<api-host>.p.rapidapi.com/<endpoint-path>",
          json=raw,
          status=200,
      )

      result = fetch_today_matches(api_key="fake-key")

      assert isinstance(result, list)
      assert all(set(m.keys()) == {"match_id", "status", "player1", "player2", "score"} for m in result)
  ```

  Fill in `<list-key-you-found>` and the URL with the real values from Step 2 — these are not placeholders left for later, they must be the actual keys/URL you observed before this step is considered done.

- [ ] **Step 4: Run tests to verify they fail**

  Run: `pytest tests/test_fetch_matches.py -v`
  Expected: FAIL with `ModuleNotFoundError` or `ImportError` (module doesn't exist yet)

- [ ] **Step 5: Implement `wimbledon/fetch_matches.py`**

  Write the module using the real field names/URL you identified. The shape (with placeholder-style names replaced by what you actually found) looks like:

  ```python
  # wimbledon/fetch_matches.py
  import requests

  API_HOST = "<api-host>.p.rapidapi.com"
  MATCHES_URL = f"https://{API_HOST}/<endpoint-path>"

  STATUS_MAP = {
      "<raw not-started value>": "not_started",
      "<raw in-progress value>": "in_progress",
      "<raw finished value>": "finished",
  }


  def normalize_match(raw: dict) -> dict:
      return {
          "match_id": str(raw["<match-id-key>"]),
          "status": STATUS_MAP.get(raw["<status-key>"], "not_started"),
          "player1": raw["<player1-key>"],
          "player2": raw["<player2-key>"],
          "score": raw["<score-key>"],
      }


  def fetch_today_matches(api_key: str) -> list[dict]:
      response = requests.get(
          MATCHES_URL,
          headers={
              "X-RapidAPI-Key": api_key,
              "X-RapidAPI-Host": API_HOST,
          },
          timeout=15,
      )
      response.raise_for_status()
      raw_matches = response.json()["<list-key-you-found>"]
      return [normalize_match(m) for m in raw_matches]
  ```

  Replace every `<...>` with the literal values you found in Step 2 — the committed file must contain no angle-bracket placeholders.

- [ ] **Step 6: Run tests to verify they pass**

  Run: `pytest tests/test_fetch_matches.py -v`
  Expected: PASS (3 passed)

- [ ] **Step 7: Install test dependencies and commit**

  ```bash
  pip install requests pytest responses
  git add wimbledon/__init__.py wimbledon/fetch_matches.py tests/test_fetch_matches.py tests/fixtures/raw_sample_response.json tests/fixtures/raw_sample_response_historical.json
  git commit -m "Add fetch_matches module with real Wimbledon API integration"
  ```

---

### Task 2: Implement `state_store.py`

**Files:**
- Create: `wimbledon/state_store.py`
- Test: `tests/test_state_store.py`

**Interfaces:**
- Consumes: nothing from other tasks
- Produces: `load_state(path: str) -> dict` (always returns a dict with key `notified_match_ids: list[str]`), `save_state(path: str, state: dict) -> None`

- [ ] **Step 1: Write the failing tests**

  ```python
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
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `pytest tests/test_state_store.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'wimbledon.state_store'`

- [ ] **Step 3: Implement `wimbledon/state_store.py`**

  ```python
  # wimbledon/state_store.py
  import json
  import os

  DEFAULT_STATE = {"notified_match_ids": []}


  def load_state(path: str) -> dict:
      if not os.path.exists(path):
          return dict(DEFAULT_STATE)
      with open(path, "r", encoding="utf-8") as f:
          return json.load(f)


  def save_state(path: str, state: dict) -> None:
      with open(path, "w", encoding="utf-8") as f:
          json.dump(state, f, indent=2)
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `pytest tests/test_state_store.py -v`
  Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

  ```bash
  git add wimbledon/state_store.py tests/test_state_store.py
  git commit -m "Add state_store module for tracking notified matches"
  ```

---

### Task 3: Implement `notifier.py` — digest message building

**Files:**
- Create: `wimbledon/notifier.py`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Consumes: match dicts in the Internal Data Contract shape (`match_id`, `status`, `player1`, `player2`, `score`)
- Produces: `build_digest_message(matches: list[dict]) -> list[str]` — always returns a list of one or more message chunks, each `<= 4096` characters

- [ ] **Step 1: Write the failing tests**

  ```python
  # tests/test_notifier.py
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
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `pytest tests/test_notifier.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'wimbledon.notifier'`

- [ ] **Step 3: Implement the digest-building part of `wimbledon/notifier.py`**

  ```python
  # wimbledon/notifier.py
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
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `pytest tests/test_notifier.py -v`
  Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

  ```bash
  git add wimbledon/notifier.py tests/test_notifier.py
  git commit -m "Add digest message building to notifier module"
  ```

---

### Task 4: Extend `notifier.py` — Telegram sending

**Files:**
- Modify: `wimbledon/notifier.py`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Consumes: `TELEGRAM_MAX_LENGTH`, `build_digest_message` (already defined in this file from Task 3)
- Produces: `send_telegram_message(bot_token: str, chat_id: str, text: str) -> None`, raising `requests.RequestException` (or a subclass) on any failure — callers in `main.py` are responsible for catching it

- [ ] **Step 1: Write the failing tests**

  Append to `tests/test_notifier.py`:

  ```python
  import pytest
  import responses

  from wimbledon.notifier import send_telegram_message


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
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `pytest tests/test_notifier.py -v`
  Expected: FAIL with `ImportError: cannot import name 'send_telegram_message'`

- [ ] **Step 3: Implement `send_telegram_message`**

  Add to `wimbledon/notifier.py`:

  ```python
  import requests


  def send_telegram_message(bot_token: str, chat_id: str, text: str) -> None:
      url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
      response = requests.post(
          url,
          json={"chat_id": chat_id, "text": text},
          timeout=15,
      )
      response.raise_for_status()
  ```

  (Add the `import requests` line at the top of the file alongside the existing constants.)

- [ ] **Step 4: Run tests to verify they pass**

  Run: `pytest tests/test_notifier.py -v`
  Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

  ```bash
  git add wimbledon/notifier.py tests/test_notifier.py
  git commit -m "Add Telegram sending to notifier module"
  ```

---

### Task 5: Implement `main.py` orchestration

**Files:**
- Create: `main.py`
- Create: `state/wimbledon_state.json`
- Create: `requirements.txt`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: `wimbledon.fetch_matches.fetch_today_matches`, `wimbledon.state_store.load_state`/`save_state`, `wimbledon.notifier.build_digest_message`/`send_telegram_message`
- Produces: `run(api_key: str, bot_token: str, chat_id: str, state_path: str) -> None`

- [ ] **Step 1: Write the failing tests**

  ```python
  # tests/test_main.py
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
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `pytest tests/test_main.py -v`
  Expected: FAIL with `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Implement `main.py`**

  ```python
  # main.py
  import os

  import requests

  from wimbledon.fetch_matches import fetch_today_matches
  from wimbledon.notifier import build_digest_message, send_telegram_message
  from wimbledon.state_store import load_state, save_state

  DEFAULT_STATE_PATH = "state/wimbledon_state.json"


  def run(api_key: str, bot_token: str, chat_id: str, state_path: str = DEFAULT_STATE_PATH) -> None:
      state = load_state(state_path)
      already_notified = set(state["notified_match_ids"])

      try:
          matches = fetch_today_matches(api_key)
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
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `pytest tests/test_main.py -v`
  Expected: PASS (5 passed)

- [ ] **Step 5: Create the initial state file**

  ```bash
  mkdir -p state
  ```

  Create `state/wimbledon_state.json`:

  ```json
  {
    "notified_match_ids": []
  }
  ```

- [ ] **Step 6: Create `requirements.txt`**

  ```
  requests
  ```

  (`pytest` and `responses` are test-only dependencies; keep them out of the runtime requirements file used by the GitHub Actions job. Install them separately for local development: `pip install pytest responses`.)

- [ ] **Step 7: Run the full test suite**

  Run: `pytest -v`
  Expected: all tests across `test_fetch_matches.py`, `test_state_store.py`, `test_notifier.py`, `test_main.py` PASS

- [ ] **Step 8: Commit**

  ```bash
  git add main.py state/wimbledon_state.json requirements.txt tests/test_main.py
  git commit -m "Add main orchestration entrypoint"
  ```

---

### Task 6: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/wimbledon-notify.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `main.py` as the executable entrypoint; `TENNIS_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` as required GitHub Secrets
- Produces: nothing consumed by other tasks — this is the final task

- [ ] **Step 1: Write the workflow file**

  ```yaml
  # .github/workflows/wimbledon-notify.yml
  name: Wimbledon Notify

  on:
    schedule:
      - cron: '0 * * * *'
    workflow_dispatch:

  permissions:
    contents: write

  jobs:
    notify:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - uses: actions/setup-python@v5
          with:
            python-version: '3.12'

        - name: Install dependencies
          run: pip install -r requirements.txt

        - name: Run notifier
          env:
            TENNIS_API_KEY: ${{ secrets.TENNIS_API_KEY }}
            TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
            TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          run: python main.py

        - name: Commit updated state
          run: |
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add state/wimbledon_state.json
            git diff --staged --quiet || git commit -m "Update Wimbledon notification state"
            git push
  ```

- [ ] **Step 2: Document required secrets in `README.md`**

  Replace the contents of `README.md` with:

  ```markdown
  # WimbledonScore

  溫布頓比賽結果 Telegram 通知服務。每小時透過 GitHub Actions 檢查 Wimbledon 比賽是否有新結束的場次，若有則發送摘要訊息到 Telegram。

  ## 設定

  在 repo 的 Settings → Secrets and variables → Actions 新增以下三個 secrets：

  - `TENNIS_API_KEY` — 網球比分 API 的金鑰
  - `TELEGRAM_BOT_TOKEN` — Telegram Bot 的 token
  - `TELEGRAM_CHAT_ID` — 要接收通知的 chat ID

  ## 本機執行測試

  ```bash
  pip install -r requirements.txt
  pip install pytest responses
  pytest -v
  ```

  ## 手動觸發

  到 GitHub repo 的 Actions 分頁 → Wimbledon Notify → Run workflow，可以手動觸發一次執行，用來驗證設定是否正確。
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add .github/workflows/wimbledon-notify.yml README.md
  git commit -m "Add GitHub Actions workflow for scheduled Wimbledon notifications"
  ```

- [ ] **Step 4: Push and manually verify**

  ```bash
  git push
  ```

  Then in the GitHub UI: go to the Actions tab, select "Wimbledon Notify", click "Run workflow" once the three secrets are set. Confirm the run completes (green check) or, if secrets aren't set yet, confirm it fails with a clear `KeyError`/missing-env-var message rather than an unrelated crash.

---

## Post-Plan Notes

- If Task 5's send-failure path (`test_run_does_not_update_state_when_send_fails`) triggers in production after the first of several digest chunks already sent successfully, the next run will resend that first chunk's matches too — this duplicate-on-partial-failure is an accepted tradeoff per the design spec (state is never marked notified before a confirmed send) and is not something to "fix" without discussing it as a new design change.
