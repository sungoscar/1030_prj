from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from activities.router import router as activities_router
from routers.registration_form import router as registration_form_router
from routers.registrations import router as registrations_router


app = FastAPI(title="Hackthon 活動平台")
# 共用同一個 app，保留各組員的獨立 Router。
app.include_router(activities_router)
app.include_router(registration_form_router)
app.include_router(registrations_router)


@app.get("/", include_in_schema=False)
def root(request: Request):
    return RedirectResponse(request.url_for("list_activities"), status_code=303)
