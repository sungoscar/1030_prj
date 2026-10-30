# Hackthon：活動管理與報名清單

整合 UI 組員的活動新增、活動清單，以及既有的活動報名清單，使用同一個 FastAPI app。
**填寫活動報名資料的第二項模組尚未接入**；活動清單會顯示「報名功能尚未接入」，沒有導向不存在的報名頁。
沿用 `database/schema.sql` 的 `activities(id, title, ...)` 與
`registrations(id, activity_id, name, phone, ...)`，沒有修改共用資料表。

## 安裝與啟動（PowerShell，Python 3.10 以上）

在專案根目錄執行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

編輯 `.env`，將 `DATABASE_URL` 設成小組 PostgreSQL 的實際連線網址。
帳號或密碼中的特殊字元需使用 URL 編碼；也可以直接設定同名環境變數，優先於 `.env`。
`.env` 已加入 `.gitignore`，請勿提交真實連線資訊。

請確認指定資料庫已由負責資料庫的組員建立 `database/schema.sql` 中的資料表。
本程式不會自動執行 schema、不會建立、刪除或重建共用資料。

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

瀏覽 `http://127.0.0.1:8000/activities/1/registrations`，將 `1` 換成既有活動編號。
有報名者時顯示編號、姓名、電話及「目前報名人數：X 人」；
沒有報名者時顯示「目前尚無報名資料」與 0 人；活動不存在則回傳 404。
未設定連線或無法連線時回傳 503；非整數編號回傳 422。
根路徑 `/` 會導向活動清單，API 文件位於 `/docs`。

| 路由 | 功能 |
|---|---|
| `GET /` | 導向活動清單 |
| `GET /activities` | 活動清單、報名截止狀態與查看報名清單連結 |
| `GET /activities/new` | 新增活動表單 |
| `POST /activities` | 驗證並新增活動，成功後以 303 導向清單 |
| `GET /activities/{activity_id}/registrations` | 活動報名者、電話與總人數 |

## 與組員整合

- `activities/router.py` 與 `routers/registrations.py` 都是獨立 `APIRouter`，`main.py` 掛載兩者。
  若組員已有主程式，保留其 app 與功能，只加入：

  ```python
  from activities.router import router as activities_router
  from routers.registrations import router as registrations_router

  app.include_router(activities_router)
  app.include_router(registrations_router)
  ```

- 活動清單的每筆活動可加入下列 Jinja2 連結（依組員的模板變數名稱調整）：

  ```html
  <a href="{{ url_for('registration_list', activity_id=activity.id) }}">查看報名清單</a>
  ```

- 活動新增沿用 UI 組員的欄位、日期解析、名稱長度與截止時間驗證；資料採參數化 SQL 寫入。
- 活動報名清單保留原路由；未新增報名寫入 API，待負責第二項功能的組員提供 Router 後接入。
- `db.py` 提供共用 `get_connection` dependency，回傳採用 `dict_row` 的 psycopg 連線。
  活動管理已改接此 dependency，不再使用 psycopg2 或 `DB_HOST/DB_NAME/DB_USER/DB_PASSWORD`。
- `templating.py` 統一以絕對路徑載入模板；`templates/base.html` 提供共用樣式與導覽。
  活動模板位於 `templates/activities/`，報名清單位於 `templates/registrations/`。
  連結與表單使用路由名稱產生網址，支援掛載前綴；沒有額外前端框架或靜態路徑。
- `activities/dev_app.py` 保留舊啟動路徑，但直接使用共用 `main.app`，不建立另一套 app。
- 所有套件由根目錄 `requirements.txt` / `requirements-dev.txt` 管理；表單解析新增 `python-multipart`。
- SQL 以 `%s` 與獨立參數查詢，單次 `LEFT JOIN` 保留空活動；人數由同次查詢的報名資料長度計算。

## 測試

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

一般測試使用替代連線驗證 HTML、統計、空清單、404、輸入驗證、HTML 跳脫、模板路徑與連線錯誤處理。
沒有 `TEST_DATABASE_URL` 時，9 項 PostgreSQL 整合測試會明確標記為 skipped，不能視為真實資料庫測試通過。

如有可用的 PostgreSQL 測試連線，可於目前的 PowerShell session 設定後執行：

```powershell
$env:TEST_DATABASE_URL = 'postgresql://your_user:your_password@localhost:5432/your_test_database'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

整合測試只在該連線建立依原始 schema 產生的 **TEMP 暫存表**，
`search_path` 限制為 `pg_temp`，測試資料只寫入暫存表，最後 rollback 並關閉連線。
不會刪除、重建或讀寫現有的正式資料表。測試帳號需具備連線與建立暫存表權限。
整合測試驗證活動新增與日期儲存、成功訊息、HTML 跳脫、開放與截止狀態、所有清單連結、
跨模組導覽、不同活動的報名資料隔離、人數、空活動及不存在活動。
UI 原先的匯入即執行測試已改為 pytest fixture，匯入測試檔案不會新增或刪除資料。

## 本次實際驗證（2026-10-30）

- Python 3.14.8、PostgreSQL 17.10；測試資料只寫入隔離 PostgreSQL 實例，pytest 使用連線專屬 TEMP 表。
- 整合 `origin/feature/ui`（`45f7391`）後：**36 passed**，包含既有 15 項與新增 21 項 UI/整合測試；
  其中 9 項使用真實 PostgreSQL 暫存表。
- `pip check` 通過，套件相依性無衝突。
- 實際啟動 Uvicorn，透過 HTTP 驗證首頁導向、活動表單、新增後的 303 導向、成功訊息、
  使用另一條資料庫連線確認新增資料已提交，以及 2/1/0 人清單與 404。
- `hackathon` 僅做唯讀頁面檢查，整合測試前後的活動與報名筆數相同；沒有向該資料庫加入假資料。
- 已在瀏覽器檢視活動清單、新增表單、報名清單及共用導覽；窄視窗的表格採水平捲動。
- 套件的 TestClient 目前有一項 httpx 棄用警告，不影響本次測試結果。
- 第二項「活動報名」尚無 Router 可整合，新增報名與截止後禁止報名的完整流程仍待該模組提供。
