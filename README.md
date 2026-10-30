# Hackthon：活動報名清單模組

此模組只提供 **查看指定活動的報名清單**，不包含活動管理、活動報名或活動清單。
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
根路徑 `/` 沒有活動清單，API 文件位於 `/docs`。

## 與組員整合

- `routers/registrations.py` 是獨立 `APIRouter`，`main.py` 僅建立 app 並掛載此 Router。
  若組員已有主程式，保留其 app 與功能，只加入：

  ```python
  from routers.registrations import router as registrations_router

  app.include_router(registrations_router)
  ```

- 活動清單的每筆活動可加入下列 Jinja2 連結（依組員的模板變數名稱調整）：

  ```html
  <a href="{{ url_for('registration_list', activity_id=activity.id) }}">查看報名清單</a>
  ```

- 路由為 `GET /activities/{activity_id}/registrations`，沒有新增活動管理或報名寫入 API。
- `db.py` 提供共用 `get_connection` dependency，回傳採用 `dict_row` 的 psycopg 連線。
  日後接入組員的連線模組時，沿用其連線生命週期，並確保查詢結果可依欄位名稱讀取。
- 模板放在 `templates/registrations/list.html`，使用絕對模板路徑與模板內的樣式，
  無須掛載共用靜態路徑或引入前端框架。
- SQL 以 `%s` 與獨立參數查詢，單次 `LEFT JOIN` 保留空活動；人數由同次查詢的報名資料長度計算。

## 測試

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

一般測試使用替代連線驗證 HTML、統計、空清單、404、輸入驗證、HTML 跳脫、模板路徑與連線錯誤處理。
沒有 `TEST_DATABASE_URL` 時，4 項 PostgreSQL 整合測試會明確標記為 skipped，不能視為真實資料庫測試通過。

如有可用的 PostgreSQL 測試連線，可於目前的 PowerShell session 設定後執行：

```powershell
$env:TEST_DATABASE_URL = 'postgresql://your_user:your_password@localhost:5432/your_test_database'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

整合測試只在該連線建立依原始 schema 產生的 **TEMP 暫存表**，
`search_path` 限制為 `pg_temp`，測試資料只寫入暫存表，最後 rollback 並關閉連線。
不會刪除、重建或讀寫現有的正式資料表。測試帳號需具備連線與建立暫存表權限。
整合測試驗證兩個不同活動的報名資料不混用、真實查詢結果的人數、空活動及不存在活動。

## 本次實際驗證（2026-10-30）

- Python 3.14.8、PostgreSQL 17.10；於專案內建立獨立測試實例，未使用既有或共用資料庫。
- 完整測試結果：**15 passed**，包含 11 項一般測試及 4 項真實 PostgreSQL 整合測試。
- `pip check` 通過，套件相依性無衝突。
- 實際啟動 Uvicorn，透過 HTTP 驗證 API 文件、兩個活動分別為 2 人與 1 人、
  另一活動為 0 人，以及不存在活動的 404；使用正式 `db.py` 連線與原始 schema 建立的隔離測試表。
- 套件的 TestClient 目前有一項 httpx 棄用警告，不影響本次測試結果。
- 尚未驗證小組共用資料庫的連線、實際資料，以及其他兩個模組的整合；
  原因是目前沒有共用連線設定，且此 checkout 尚無其他模組。
