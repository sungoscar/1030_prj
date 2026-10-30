
from fastapi import FastAPI

from routers.registrations import router as registrations_router
from routers.registration_form import router as registration_form_router


app = FastAPI(title="Hackathon 活動平台")

# 組員的報名清單功能
app.include_router(registrations_router)

# 自己負責的活動報名功能
app.include_router(registration_form_router)
