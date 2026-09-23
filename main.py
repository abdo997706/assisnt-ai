import os
import secrets
from fastapi import FastAPI, Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
import pymysql

app = FastAPI(title="Assistant AI Server")

# 1. الاتصال التلقائي بقاعدة بيانات MySQL المربوطة في Railway
def get_db_connection():
    return pymysql.connect(
        host=os.getenv("MYSQLHOST", "localhost"),
        user=os.getenv("MYSQLUSER", "root"),
        password=os.getenv("MYSQLPASSWORD", ""),
        database=os.getenv("MYSQLDATABASE", "railway"),
        port=int(os.getenv("MYSQLPORT", 3306)),
        cursorclass=pymysql.cursors.DictCursor
    )

# تعيين الهيدر الذي سيرسله المستخدم وفيه المفتاح باسم (x-api-key)
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# =========================================================
# 2. دالة الفحص والتحقق (Middleware) لحماية السيرفر بالـ API Key
# =========================================================
async def get_current_user_by_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="مفتاح الـ API Key مفقود!")
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # الفحص داخل جدول قاعدة البيانات المتصل بـ Railway
            sql = "SELECT user_id FROM api_keys WHERE api_key = %s AND status = 'active'"
            cursor.execute(sql, (api_key,))
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="مفتاح الـ API Key غير صحيح أو تم إيقافه")
            return result['user_id']
    finally:
        connection.close()

# =========================================================
# 3. كود بناء وتوليد الـ API Key للمستخدم
# =========================================================
@app.post("/api/generate-key")
def generate_api_key(user_id: int):
    # توليد مفتاح عشوائي آمن مشفر يبدأ برمز خاص بتطبيقك
    raw_key = secrets.token_hex(32)
    custom_api_key = f"sk_assist_{raw_key}"
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = "INSERT INTO api_keys (user_id, api_key) VALUES (%s, %s)"
            cursor.execute(sql, (user_id, custom_api_key))
        connection.commit()
        
        # يظهر المفتاح مرة واحدة فقط للمستخدم لحفظه
        return {
            "message": "تم توليد مفتاح الـ API بنجاح. احفظه في مكان آمن!",
            "api_key": custom_api_key
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="فشل في حفظ وتوليد المفتاح")
    finally:
        connection.close()

# =========================================================
# 4. سيرفر الـ API المحمي (مثال على مسار تخزين أو جلب البيانات)
# =========================================================
@app.get("/api/v1/data")
def get_secure_data(user_id: int = Depends(get_current_user_by_api_key)):
    return {
        "status": "success",
        "message": "مرحباً بك! تم الدخول إلى السيرفر والتخزين بنجاح باستخدام الـ API Key.",
        "user_id": user_id
    }