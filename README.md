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
