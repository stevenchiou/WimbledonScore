# Wimbledon Telegram Notifier — Design

## 目的

在 Wimbledon 網球賽事期間，自動偵測比賽結束並透過 Telegram 發送結果通知，不需要手動盯盤。

## 範圍

- 追蹤範圍：所有 Wimbledon 正賽（單打/雙打不特別篩選，依 API 回傳的當日賽事為準）
- 通知時機：**只在比賽結束時**通知，不通知開賽、不通知中途比分
- 通知對象：固定發送到使用者自己的 Telegram Bot 對應的單一 chat（無多使用者訂閱機制）
- 不包含：指定選手篩選功能（曾評估透過 Telegram 指令動態維護重點選手清單，但因需與比分查詢共用每小時排程、指令生效延遲最長達 1 小時，與 Telegram bot 一般即時互動的預期不符，故不列入此版本範圍）

## 架構總覽

一個 Python 腳本，由 **GitHub Actions 排程工作流程**觸發（每小時一次，全年運作），流程為：

```
抓取當日 Wimbledon 比賽狀態
  → 與 repo 內儲存的上次狀態比對，找出「非 finished → finished」的比賽
  → 若有一場以上比賽轉為 finished，組成一則摘要訊息（含比分）
  → 透過 Telegram Bot API 發送
  → 更新狀態檔（記錄已通知的比賽 ID）並 commit 回 repo
```

無需常駐伺服器、無需資料庫；GitHub repo 同時作為程式碼與狀態儲存的載體。

## 元件

| 元件 | 職責 |
|---|---|
| `fetch_matches.py` | 呼叫 Wimbledon 比分 API，取得當日所有比賽及狀態（未開賽/進行中/已結束）與比分 |
| `state_store.py` | 讀寫 `state/wimbledon_state.json`：已通知過的比賽 ID 清單 |
| `notifier.py` | 組裝摘要訊息文字（含超過 Telegram 4096 字元自動分段）、呼叫 Telegram Bot API 發送 |
| `main.py` | 串接以上三者：抓資料 → 比對差異 → 有變化才發通知 → 成功後才寫回狀態 |
| `.github/workflows/wimbledon-notify.yml` | 定義每小時排程、注入 Secrets（比分 API Key、Telegram Bot Token、Chat ID）、執行完後 commit 狀態檔 |

命名規範：程式碼、目錄、變數中涉及賽事名稱的英文一律使用 `Wimbledon`（含大小寫），不使用其他拼法或全小寫變體。

## 資料流與偵測邏輯

1. 每次執行呼叫 API 取得「今日 Wimbledon 賽事列表」，每場比賽含 `match_id`、`status`（`not_started` / `in_progress` / `finished`）、對戰雙方、比分
2. 讀取 `state/wimbledon_state.json` 中上次記錄的「已通知比賽 ID 集合」
3. 篩選出 `status == finished` 且尚未通知過的比賽
4. 若篩選結果為空 → 正常結束，不發送、不更新狀態
5. 若篩選結果非空 → 組裝成一則摘要訊息（列出每場比賽對戰雙方與比分），呼叫 Telegram Bot API 發送
6. 發送成功後，才將這批比賽 ID 加入已通知集合，寫回 JSON 並 commit
7. 若當日無 Wimbledon 賽事（非賽季或當日休兵）→ 視為正常情況，直接結束

## 錯誤處理

- **比分 API 呼叫失敗**（額度用盡、逾時、格式異常）：記錄錯誤，直接結束本次執行；不更新狀態、不重試，等下一次排程自然重跑
- **Telegram 發送失敗**：記錄錯誤結束，**不**將本次比賽標記為已通知，避免「發送失敗卻被當成已發送」；下次排程會用同一批已結束比賽再次嘗試
- **非賽季/當日無賽事**：不算錯誤，正常結束

## 測試方式

- 用 fixture（假的 API 回應 JSON）測試狀態比對邏輯：驗證「上次狀態」vs「這次狀態」比對後，只挑出新轉為 finished 且未通知過的比賽
- 用 fixture 測試訊息組裝邏輯：多場比賽同時結束時的摘要格式、超長訊息的分段邏輯
- Telegram 發送與比分 API 呼叫皆以 mock 取代，不在測試中呼叫真實外部服務

## 待實作階段確認的事項

- 具體採用哪個免費額度 Wimbledon/網球比分 API（候選：RapidAPI 上的 Tennis API 系列），需在實作時申請並驗證其 `status` 欄位是否符合本設計假設
- Telegram Bot Token 與 Chat ID 的取得與設定（存入 GitHub Secrets）
