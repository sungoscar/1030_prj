from fastapi import FastAPI

from routers.registrations import router as registrations_router


app = FastAPI(title="Hackthon 活動平台")
# 只掛載報名清單；其他組員可在此加入各自的 Router。
app.include_router(registrations_router)
