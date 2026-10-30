import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from fastapi import HTTPException
from psycopg.rows import dict_row


# 固定從專案目錄載入，且不覆蓋系統已設定的環境變數。
load_dotenv(Path(__file__).resolve().parent / ".env")


def get_connection() -> Iterator[psycopg.Connection]:
    """供各 Router 共用，每次請求結束後關閉資料庫連線。"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(status_code=503, detail="尚未設定 DATABASE_URL 資料庫連線。")

    try:
        connection = psycopg.connect(
            database_url, row_factory=dict_row, connect_timeout=5, autocommit=True
        )
    except (psycopg.Error, ValueError):
        # 不將可能含帳號、密碼的連線錯誤回傳給使用者。
        raise HTTPException(status_code=503, detail="暫時無法連線資料庫。") from None

    try:
        yield connection
    finally:
        connection.close()
