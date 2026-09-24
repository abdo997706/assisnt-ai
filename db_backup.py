# -*- coding: utf-8 -*-
"""
db_backup.py
نسخة احتياطية للبيانات على MySQL - بتشتغل جنب ملفات JSON المحلية مش بدالها.
لو MySQL مش متاح أو حصل فيه خطأ، الموقع بيكمل شغل عادي بملفات JSON بس.
لو ملفات JSON اتمسحت (زي ما بيحصل أحيانًا عند إعادة نشر السيرفر)، البيانات بترجع من MySQL تلقائيًا.

يعتمد على متغيرات البيئة اللي Railway بيحطها تلقائيًا لما تضيف MySQL:
MYSQL_URL أو (MYSQLHOST, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE, MYSQLPORT)
"""

import os
import json

_connection = None
_available = None  # None = لسه مجربناش، True/False = جربنا وطلعت النتيجة


def _get_connection():
    """بيرجع اتصال MySQL جاهز، أو None لو مش متاح."""
    global _connection, _available

    if _available is False:
        return None
    if _connection is not None:
        try:
            _connection.ping(reconnect=True)
            return _connection
        except Exception:
            _connection = None

    try:
        import pymysql
    except ImportError:
        _available = False
        return None

    url = os.environ.get("MYSQL_URL") or os.environ.get("MYSQL_PUBLIC_URL")
    try:
        if url:
            # صيغة mysql://user:pass@host:port/dbname
            from urllib.parse import urlparse
            parsed = urlparse(url)
            conn = pymysql.connect(
                host=parsed.hostname,
                port=parsed.port or 3306,
                user=parsed.username,
                password=parsed.password or "",
                database=parsed.path.lstrip("/"),
                charset="utf8mb4",
                autocommit=True,
                connect_timeout=5,
            )
        else:
            host = os.environ.get("MYSQLHOST")
            if not host:
                _available = False
                return None
            conn = pymysql.connect(
                host=host,
                port=int(os.environ.get("MYSQLPORT", 3306)),
                user=os.environ.get("MYSQLUSER", "root"),
                password=os.environ.get("MYSQLPASSWORD", ""),
                database=os.environ.get("MYSQLDATABASE", "railway"),
                charset="utf8mb4",
                autocommit=True,
                connect_timeout=5,
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS json_store (
                    file_key VARCHAR(255) PRIMARY KEY,
                    data LONGTEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) CHARACTER SET utf8mb4
                """
            )
        _connection = conn
        _available = True
        return _connection
    except Exception as e:
        print(f"⚠️ MySQL backup غير متاح دلوقتي: {e}")
        _available = False
        return None


def backup_save(file_key, data):
    """بيحفظ نسخة من البيانات في MySQL. بيفشل بهدوء لو MySQL مش متاح - مش بيوقف الموقع."""
    conn = _get_connection()
    if conn is None:
        return False
    try:
        payload = json.dumps(data, ensure_ascii=False)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO json_store (file_key, data) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE data = VALUES(data)
                """,
                (file_key, payload),
            )
        return True
    except Exception as e:
        print(f"⚠️ فشل حفظ نسخة احتياطية على MySQL لـ {file_key}: {e}")
        return False


def backup_load(file_key):
    """بيرجع البيانات من MySQL، أو None لو مش موجودة أو MySQL مش متاح."""
    conn = _get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM json_store WHERE file_key = %s", (file_key,))
            row = cur.fetchone()
            if row and row[0]:
                return json.loads(row[0])
    except Exception as e:
        print(f"⚠️ فشل قراءة نسخة احتياطية من MySQL لـ {file_key}: {e}")
    return None
