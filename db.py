"""Module kết nối và xử lý cơ sở dữ liệu MySQL cho Hệ thống Quản lý Ký túc xá Sinh viên.

Cung cấp các hàm:
- get_connection(): Khởi tạo kết nối MySQL utf8mb4.
- fetch_df(query, params): Thực thi truy vấn SELECT và trả về pandas.DataFrame.
- execute_query(query, params): Thực thi INSERT/UPDATE/DELETE với commit/rollback và bóc tách lỗi Trigger 45000.
- execute_transaction(operations): Thực thi chuỗi câu lệnh trong một transaction nguyên tử với commit/rollback tự động.
"""

import os
from pathlib import Path
import mysql.connector
import pandas as pd
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def get_connection():
    """Khởi tạo và trả về đối tượng kết nối MySQL với bảng mã utf8mb4."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "ql_ky_tuc_xa"),
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        autocommit=False,
    )


def fetch_df(query: str, params=None) -> pd.DataFrame:
    """Thực thi câu truy vấn SELECT và trả về pandas.DataFrame."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description] if cursor.description else []
        return pd.DataFrame(rows, columns=columns)
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def execute_query(query: str, params=None) -> tuple[bool, str]:
    """Thực thi câu lệnh INSERT / UPDATE / DELETE với transaction an toàn.

    Trả về:
        (True, "Thành công") nếu lệnh chạy trọn vẹn.
        (False, err.msg) nếu gặp lỗi từ CSDL (đặc biệt là lỗi từ Trigger SIGNAL SQLSTATE '45000').
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        conn.commit()
        return True, "Thành công"
    except mysql.connector.Error as err:
        if conn and conn.is_connected():
            conn.rollback()
        return False, err.msg
    except Exception as ex:
        if conn and conn.is_connected():
            conn.rollback()
        return False, str(ex)
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def execute_transaction(operations: list[tuple[str, tuple]]) -> tuple[bool, str]:
    """Thực thi chuỗi câu lệnh SQL trong cùng một Transaction nguyên tử.

    Tham số:
        operations: Danh sách các tuple (query, params).

    Trả về:
        (True, "Thành công") nếu toàn bộ câu lệnh thực thi và commit trọn vẹn.
        (False, err.msg) nếu có bất kỳ lỗi nào xảy ra; tự động rollback CSDL.
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        conn.start_transaction()
        cursor = conn.cursor()
        for query, params in operations:
            cursor.execute(query, params or ())
            if cursor.with_rows:
                cursor.fetchall()
        conn.commit()
        return True, "Thành công"
    except mysql.connector.Error as err:
        if conn and conn.is_connected():
            conn.rollback()
        return False, err.msg
    except Exception as ex:
        if conn and conn.is_connected():
            conn.rollback()
        return False, str(ex)
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()

