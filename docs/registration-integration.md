# 活動報名整合紀錄

本次只在 `integration-registration` 進行，起點為 main 的 `05c1e9c`。
將 `1dffc78` cherry-pick 後解決衝突，保留原 Commit 作者 nick；不合併回 main 或 Push。

## Commit 比較

- `71e3b1c` 是該分支的根 Commit，只有 `database/1030_prj.sql`，內容是使用舊表名的 SELECT。
- `1dffc78` 的父 Commit 為 `71e3b1c`，新增 15 個檔案，其中包含報名 Router、表單，
  以及從既有架構帶入的共用檔案和報名清單測試；沒有改動舊 SELECT 檔。
- 此分支與 main 沒有共同 Git 祖先，因此只 cherry-pick 功能 Commit，未匯入根 Commit 的舊 SQL。
- `1dffc78` 內的 `database/schema.sql`、`db.py`、`.env.example` 與 main 相同，不需遷移資料庫。

## 六項 add/add 衝突

| 檔案 | 解決方式 |
|---|---|
| `.gitignore` | 保留 main 的全部規則，包括 `.env`、虛擬環境、測試產物與 `.DS_Store` |
| `README.md` | 保留已整合 UI 的說明，再加入報名路由、限制、測試與本紀錄 |
| `main.py` | 保留活動管理、報名清單與首頁導向，額外掛載報名 Router |
| `requirements.txt` | 保留既有套件，將 python-multipart 下限統一為組員要求的 0.0.20 |
| `routers/registrations.py` | 保留 main 的共用模板與既有查詢、人數、404 行為 |
| `templates/registrations/list.html` | 保留 main 的共用版型、導覽、表格與空清單 |

報名 Router 使用現有 `get_connection`、`DATABASE_URL` 與 psycopg 3；
同步資料庫查詢改為同步 FastAPI handler。表單沿用姓名、電話與錯誤/成功提示，改繼承共用版型，
網址透過路由名稱產生，支援掛載前綴。既有 36 項測試全部保留；原 UI 測試的「尚未接入」斷言
更新為「開放活動有報名連結、截止活動無報名連結」。

## 舊 SQL 差異（未執行、未覆蓋 schema）

| 根 Commit 的舊查詢名稱 | 現有 schema 對應 |
|---|---|
| `activity` | `activities` |
| `registration` | `registrations` |
| `activity.activity_id` | `activities.id` |
| `activity.activity_name` | `activities.title` |
| `registration.registration_date` | `registrations.registered_at` |

報名程式實際使用 `registrations(activity_id, name, phone)`，與既有 schema 一致。
沿用 `UNIQUE(activity_id, name, phone)`，不新增資料表、欄位或約束，也不改動現有資料。

## 驗證

- 60 項 pytest 通過：原有 36 項 + 24 項報名測試，含 18 項真實 PostgreSQL 暫存表測試。
- 驗證成功報名後清單可見、同活動重複拒絕、不同活動不混用、截止後無法送出、欄位長度、404 與 HTML 跳脫。
- 真實 HTTP 流程於 55432 隔離資料庫驗證；`hackathon` 只讀，前後活動/報名筆數相同。
- schema、共用連線與環境範例未修改；密碼、`.env`、測試實例與產物未納入 Git。
