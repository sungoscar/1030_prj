import os, re
os.environ.update(DB_HOST="/tmp", DB_NAME="activity_signup", DB_USER="postgres")
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from activities.dev_app import app
from activities.router import get_conn

c = TestClient(app)
fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M")
now = datetime.now().replace(second=0, microsecond=0)
R = []
def check(name, ok): R.append((name, ok)); print(("PASS " if ok else "FAIL ") + name)

# 1 表單頁
r = c.get("/activities/new"); check("GET /activities/new 200", r.status_code == 200 and "活動名稱" in r.text)

# 2 新增「可報名」活動
ev1, dl1 = now + timedelta(days=10), now + timedelta(days=5)
r = c.post("/activities", data=dict(title="測試-可報名<b>", description="說明A", event_date=fmt(ev1), registration_deadline=fmt(dl1)), follow_redirects=False)
check("POST 成功 303 導向清單", r.status_code == 303 and r.headers["location"].startswith("/activities?created="))
id_open = int(r.headers["location"].split("=")[1])

# 3 新增「已截止」活動
ev2, dl2 = now + timedelta(days=3), now - timedelta(hours=1)
r = c.post("/activities", data=dict(title="測試-已截止", description="", event_date=fmt(ev2), registration_deadline=fmt(dl2)), follow_redirects=False)
id_closed = int(r.headers["location"].split("=")[1])

# 4 資料庫實際儲存值
with get_conn() as cur:
    cur.execute("select * from activities where id=%s", (id_open,)); row = cur.fetchone()
    check("DB 活動日期正確", row["event_date"] == ev1)
    check("DB 截止時間正確", row["registration_deadline"] == dl1)
    check("DB 活動說明正確", row["description"] == "說明A")
    cur.execute("select description from activities where id=%s", (id_closed,))
    check("空白說明存成 NULL", cur.fetchone()["description"] is None)

# 5 清單頁
r = c.get(f"/activities?created={id_open}")
html = r.text
check("清單出現新活動與成功訊息", "已新增活動" in html and "測試-已截止" in html)
check("標題 HTML 被跳脫(無 XSS)", "<b>" not in html.split("測試-可報名")[1][:10] and "&lt;b&gt;" in html)
def row_of(title):
    return [x for x in html.split("<tr>") if "<td>" in x and title in x][0]
ro, rc = row_of("測試-可報名"), row_of("測試-已截止")
check("可報名活動：狀態=可報名 且有『我要報名』", "可報名" in ro and f"/activities/{id_open}/register" in ro)
check("已截止活動：狀態=已截止 且『沒有』我要報名", "已截止" in rc and "/register" not in rc)
check("兩者都有『查看報名清單』", f"/activities/{id_open}/registrations" in ro and f"/activities/{id_closed}/registrations" in rc)

# 6 驗證
def bad(**kw):
    d = dict(title="x", description="", event_date=fmt(ev1), registration_deadline=fmt(dl1)); d.update(kw)
    return c.post("/activities", data=d, follow_redirects=False)
with get_conn() as cur:
    cur.execute("select count(*) n from activities"); before = cur.fetchone()["n"]
r = bad(title="   "); check("名稱空白 → 400", r.status_code == 400 and "請填寫活動名稱" in r.text)
r = bad(event_date=""); check("缺活動日期 → 400", r.status_code == 400 and "請選擇活動日期" in r.text)
r = bad(registration_deadline=""); check("缺截止時間 → 400", r.status_code == 400 and "請選擇報名截止時間" in r.text)
r = bad(event_date="亂填"); check("日期格式錯 → 400", r.status_code == 400 and "格式不正確" in r.text)
r = bad(registration_deadline=fmt(ev1 + timedelta(days=1))); check("截止晚於活動日期 → 400", r.status_code == 400 and "不可晚於" in r.text)
r = bad(title="a"*101); check("名稱過長 → 400", r.status_code == 400)
r = bad(title="保留輸入", event_date=""); check("錯誤時保留已填內容", 'value="保留輸入"' in r.text)
r = c.post("/activities", data={}, follow_redirects=False); check("完全空表單不會 500", r.status_code == 400)
with get_conn() as cur:
    cur.execute("select count(*) n from activities"); after = cur.fetchone()["n"]
check("驗證失敗不寫入資料庫", before == after)

# 7 清理本次測試資料（只刪自己建的）
with get_conn() as cur:
    cur.execute("delete from activities where id in (%s,%s)", (id_open, id_closed))
print(f"\n{sum(o for _,o in R)}/{len(R)} 通過")
