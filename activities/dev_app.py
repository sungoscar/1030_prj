"""只用來單獨測試活動模組：uvicorn activities.dev_app:app --reload
正式整合請在共用 main.py 用 include_router，不要用這個檔案。"""
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from activities.router import router

app = FastAPI()
app.include_router(router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/activities")
