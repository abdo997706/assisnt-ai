# -*- coding: utf-8 -*-
"""
server.py
السيرفر الخلفي (Backend) بتاع نسخة HTML/JS من المساعد الذكي.
"""
 
import os
import io
import json
import time
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
 
import cloud_engine
import media_tools
import db_backup
from PIL import Image
 
app = FastAPI()
 
DB_FOLDER = "data"
os.makedirs(DB_FOLDER, exist_ok=True)
USERS_FILE = os.path.join(DB_FOLDER, "users_db.json")
CHATS_FILE = os.path.join(DB_FOLDER, "chats_db.json")
VIP_CODES_FILE = os.path.join(DB_FOLDER, "vip_codes.json")
 
FREE_WINDOW_SECONDS = 3 * 60 * 60
LOCK_DURATION_SECONDS = 3 * 60 * 60
 
# ذاكرة مؤقتة (في السيرفر) للملفات/الصور اللي كل مستخدم رفعها - عشان الشات يقدر يستخدمها
session_file_context = {}
session_image_context = {}
 
 
def load_json(path, default):
    """
    بيقرا من ملف JSON المحلي أولاً (أسرع). لو الملف مش موجود (زي ما بيحصل
    أحيانًا بعد إعادة نشر السيرفر)، بيحاول يجيب نسخة احتياطية من MySQL
    ويرجّعها، ويحفظها محليًا تاني عشان المرة الجاية تبقى سريعة.
    """
    file_key = os.path.basename(path)
 
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
 
    backup = db_backup.backup_load(file_key)
    if backup is not None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(backup, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
        return backup
 
    return default
 
 
def save_json(path, data):
    """
    بيحفظ في ملف JSON المحلي (المصدر الأساسي والسريع)، وبعدها بيحاول
    يحفظ نسخة طبق الأصل في MySQL كنسخة احتياطية. لو MySQL مش متاح دلوقتي،
    الحفظ المحلي بيكمل عادي من غير أي تعطيل للموقع.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
 
    file_key = os.path.basename(path)
    db_backup.backup_save(file_key, data)
 
 
def ensure_usage_fields(record):
    changed = False
    if "window_start" not in record:
        record["window_start"] = time.time()
        changed = True
    if "is_vip" not in record:
        record["is_vip"] = False
        changed = True
    if "total_allowed_seconds" not in record:
        record["total_allowed_seconds"] = FREE_WINDOW_SECONDS
        changed = True
    return changed
 
 
def compute_usage_status(record):
    now = time.time()
    elapsed = now - record["window_start"]
    locked = False
    remaining_lock = 0
 
    if not record["is_vip"] and elapsed >= record["total_allowed_seconds"]:
        time_since_end = elapsed - record["total_allowed_seconds"]
        if time_since_end < LOCK_DURATION_SECONDS:
            locked = True
            remaining_lock = LOCK_DURATION_SECONDS - time_since_end
        else:
            record["window_start"] = now
            record["total_allowed_seconds"] = FREE_WINDOW_SECONDS
            elapsed = 0
 
    remaining_free = max(0, record["total_allowed_seconds"] - elapsed)
    return locked, remaining_lock, remaining_free
 
 
def extract_text_from_bytes(filename, data: bytes):
    name = filename.lower()
    try:
        if name.endswith((".txt", ".md")):
            return data.decode("utf-8", errors="ignore")
        elif name.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = ""
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
            return text.strip()
        elif name.endswith(".docx"):
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
        elif name.endswith(".csv"):
            import pandas as pd
            df = pd.read_csv(io.BytesIO(data))
            return df.to_string()
        elif name.endswith((".xlsx", ".xls")):
            import pandas as pd
            df = pd.read_excel(io.BytesIO(data))
            return df.to_string()
        else:
            return None
    except Exception as e:
        return f"⚠️ تعذرت قراءة الملف: {e}"
 
 
# ---------- تسجيل الدخول / الحسابات ----------
 
@app.post("/api/signup")
async def signup(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
    question = body.get("question", "").strip()
    answer = body.get("answer", "").strip()
 
    if not username or not password or not question or not answer:
        return JSONResponse({"ok": False, "error": "لازم تملى كل الحقول."}, status_code=400)
 
    users = load_json(USERS_FILE, {})
    if username in users:
        return JSONResponse({"ok": False, "error": "اسم المستخدم محجوز بالفعل."}, status_code=400)
 
    users[username] = {"password": password, "question": question, "answer": answer.lower()}
    save_json(USERS_FILE, users)
    return {"ok": True}
 
 
@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()
 
    users = load_json(USERS_FILE, {})
    record = users.get(username)
    if record and record.get("password") == password:
        return {"ok": True, "username": username}
    return JSONResponse({"ok": False, "error": "اسم المستخدم أو كلمة المرور غلط."}, status_code=401)
 
 
# ---------- نسيت كلمة المرور ----------
 
@app.post("/api/get_security_question")
async def get_security_question(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
 
    users = load_json(USERS_FILE, {})
    record = users.get(username)
    if not record or not isinstance(record, dict) or "question" not in record:
        return JSONResponse({"ok": False, "error": "مفيش حساب بالاسم ده أو مفيش سؤال أمان متسجل ليه."}, status_code=404)
    return {"ok": True, "question": record["question"]}
 
 
@app.post("/api/reset_password")
async def reset_password(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    answer = body.get("answer", "").strip().lower()
    new_password = body.get("new_password", "").strip()
 
    users = load_json(USERS_FILE, {})
    record = users.get(username)
    if not record or not isinstance(record, dict):
        return JSONResponse({"ok": False, "error": "حساب غير موجود."}, status_code=404)
 
    if record.get("answer", "") != answer:
        return JSONResponse({"ok": False, "error": "الإجابة غلط."}, status_code=400)
 
    if not new_password:
        return JSONResponse({"ok": False, "error": "اكتب كلمة مرور جديدة."}, status_code=400)
 
    record["password"] = new_password
    users[username] = record
    save_json(USERS_FILE, users)
    return {"ok": True}
 
 
# ---------- نظام الوقت المسموح والأكواد ----------
 
@app.get("/api/usage/{username}")
async def get_usage(username: str):
    users = load_json(USERS_FILE, {})
    record = users.get(username)
    if not record:
        return JSONResponse({"error": "user not found"}, status_code=404)
    if not isinstance(record, dict):
        record = {"password": record}
 
    ensure_usage_fields(record)
    locked, remaining_lock, remaining_free = compute_usage_status(record)
 
    users[username] = record
    save_json(USERS_FILE, users)
 
    return {
        "locked": locked,
        "remaining_lock_seconds": remaining_lock,
        "remaining_free_seconds": remaining_free,
        "is_vip": record["is_vip"],
    }
 
 
@app.post("/api/redeem_code")
async def redeem_code(request: Request):
    body = await request.json()
    username = body.get("username")
    code = body.get("code", "").strip()
 
    codes = load_json(VIP_CODES_FILE, [])
    matched = next((c for c in codes if c.get("code") == code), None)
    if not matched:
        return JSONResponse({"ok": False, "error": "الكود غلط أو مستخدم قبل كده."}, status_code=400)
 
    codes.remove(matched)
    save_json(VIP_CODES_FILE, codes)
 
    users = load_json(USERS_FILE, {})
    record = users.get(username, {})
    if not isinstance(record, dict):
        record = {"password": record}
    ensure_usage_fields(record)
    record["total_allowed_seconds"] = record.get("total_allowed_seconds", FREE_WINDOW_SECONDS) + matched.get("hours", 0) * 3600
    users[username] = record
    save_json(USERS_FILE, users)
 
    return {"ok": True, "hours_added": matched.get("hours", 0)}
 
 
# ---------- الشاتات ----------
 
@app.get("/api/chats/{username}")
async def get_chats(username: str):
    all_chats = load_json(CHATS_FILE, {})
    user_chats = all_chats.get(username, {})
    if not user_chats:
        user_chats = {"الشات الافتراضي": [{"role": "assistant", "content": "🤖 أهلاً بيك! اكتب رسالتك تحت."}]}
        all_chats[username] = user_chats
        save_json(CHATS_FILE, all_chats)
    return user_chats
 
 
@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    username = body.get("username")
    chat_id = body.get("chat_id", "الشات الافتراضي")
    message = body.get("message", "")
 
    users = load_json(USERS_FILE, {})
    user_record = users.get(username)
    if user_record and isinstance(user_record, dict):
        ensure_usage_fields(user_record)
        locked, remaining_lock, _ = compute_usage_status(user_record)
        users[username] = user_record
        save_json(USERS_FILE, users)
        if locked:
            return JSONResponse(
                {"error": "locked", "remaining_lock_seconds": remaining_lock},
                status_code=403,
            )
 
    all_chats = load_json(CHATS_FILE, {})
    user_chats = all_chats.setdefault(username, {})
    messages = user_chats.setdefault(chat_id, [])
 
    messages.append({"role": "user", "content": message})
 
    history = messages[:-1]
 
    system_prompt = None
    file_ctx = session_file_context.get(username)
    if file_ctx:
        system_prompt = (
            f"المستخدم رفع ملف اسمه ({file_ctx['name']}) وده محتواه:\n\n{file_ctx['text'][:8000]}\n\n"
            "استخدم المحتوى ده للإجابة على أي سؤال متعلق بالملف."
        )
 
    image = session_image_context.get(username)
 
    start = time.time()
    reply = cloud_engine.generate_gemini_response(
        message, chat_history=history, system_prompt=system_prompt, image=image
    )
    elapsed = time.time() - start
 
    messages.append({"role": "assistant", "content": reply})
    save_json(CHATS_FILE, all_chats)
 
    return {"reply": reply, "elapsed": round(elapsed, 1)}
 
 
@app.post("/api/new_chat")
async def new_chat(request: Request):
    body = await request.json()
    username = body.get("username")
    chat_name = body.get("chat_name", "").strip()
 
    all_chats = load_json(CHATS_FILE, {})
    user_chats = all_chats.setdefault(username, {})
    if chat_name and chat_name not in user_chats:
        user_chats[chat_name] = [{"role": "assistant", "content": f"🤖 تم فتح شات جديد: {chat_name}"}]
        save_json(CHATS_FILE, all_chats)
    return user_chats
 
 
@app.post("/api/delete_chat")
async def delete_chat(request: Request):
    body = await request.json()
    username = body.get("username")
    chat_name = body.get("chat_name", "").strip()
 
    all_chats = load_json(CHATS_FILE, {})
    user_chats = all_chats.setdefault(username, {})
 
    if len(user_chats) <= 1:
        return JSONResponse({"ok": False, "error": "مينفعش تمسح آخر شات موجود."}, status_code=400)
 
    if chat_name in user_chats:
        del user_chats[chat_name]
        save_json(CHATS_FILE, all_chats)
        return {"ok": True, "chats": user_chats}
 
    return JSONResponse({"ok": False, "error": "الشات ده مش موجود."}, status_code=404)
 
 
@app.post("/api/rename_chat")
async def rename_chat(request: Request):
    body = await request.json()
    username = body.get("username")
    old_name = body.get("old_name", "").strip()
    new_name = body.get("new_name", "").strip()
 
    all_chats = load_json(CHATS_FILE, {})
    user_chats = all_chats.setdefault(username, {})
 
    if not new_name:
        return JSONResponse({"ok": False, "error": "اكتب اسم جديد."}, status_code=400)
    if old_name not in user_chats:
        return JSONResponse({"ok": False, "error": "الشات ده مش موجود."}, status_code=404)
    if new_name in user_chats:
        return JSONResponse({"ok": False, "error": "الاسم ده مستخدم بالفعل."}, status_code=400)
 
    user_chats[new_name] = user_chats.pop(old_name)
    save_json(CHATS_FILE, all_chats)
    return {"ok": True, "chats": user_chats}
 
 
# ---------- رفع الملفات (للشات) ----------
 
@app.post("/api/upload")
async def upload_file(username: str = Form(...), file: UploadFile = File(...)):
    data = await file.read()
    filename = file.filename
    is_image = file.content_type is not None and file.content_type.startswith("image/")
 
    if is_image:
        img = Image.open(io.BytesIO(data))
        session_image_context[username] = img
        return {"ok": True, "filename": filename, "type": "image"}
    else:
        text = extract_text_from_bytes(filename, data)
        if text is None:
            return JSONResponse({"ok": False, "error": "نوع الملف مش مدعوم."}, status_code=400)
        session_file_context[username] = {"name": filename, "text": text}
        return {"ok": True, "filename": filename, "type": "document", "chars": len(text)}
 
 
# ---------- تعديل الصور ----------
 
@app.post("/api/edit_image")
async def edit_image(
    operation: str = Form(...),
    file: UploadFile = File(...),
    width: int = Form(None),
    height: int = Form(None),
    left: int = Form(None),
    top: int = Form(None),
    right: int = Form(None),
    bottom: int = Form(None),
    angle: float = Form(None),
    factor: float = Form(None),
    flip_mode: str = Form(None),
):
    try:
        data = await file.read()
        img = Image.open(io.BytesIO(data))
 
        if operation == "resize":
            result = media_tools.resize_image(img, width, height)
        elif operation == "crop":
            result = media_tools.crop_image(img, left, top, right, bottom)
        elif operation == "rotate":
            result = media_tools.rotate_image(img, angle)
        elif operation == "grayscale":
            result = media_tools.grayscale_image(img)
        elif operation == "brightness":
            result = media_tools.adjust_brightness(img, factor)
        elif operation == "flip":
            result = media_tools.flip_image(img, flip_mode)
        else:
            return JSONResponse({"ok": False, "error": "عملية غير معروفة."}, status_code=400)
 
        img_bytes = media_tools.image_to_bytes(result, fmt="PNG")
        return Response(content=img_bytes, media_type="image/png")
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
 
 
# ---------- تعديل الفيديو ----------
 
@app.post("/api/edit_video")
async def edit_video(
    operation: str = Form(...),
    file: UploadFile = File(...),
    start: float = Form(None),
    end: float = Form(None),
    width: int = Form(None),
    height: int = Form(None),
):
    tmp_in = None
    tmp_out = None
    try:
        data = await file.read()
        tmp_in = media_tools._save_uploaded_to_temp(data, suffix=".mp4")
 
        if operation == "trim":
            tmp_out = tmp_in.replace(".mp4", "_out.mp4")
            media_tools.trim_video(tmp_in, tmp_out, start, end)
            media_type = "video/mp4"
        elif operation == "extract_audio":
            tmp_out = tmp_in.replace(".mp4", "_out.mp3")
            media_tools.extract_audio(tmp_in, tmp_out)
            media_type = "audio/mp3"
        elif operation == "resize":
            tmp_out = tmp_in.replace(".mp4", "_out.mp4")
            media_tools.resize_video(tmp_in, tmp_out, width, height)
            media_type = "video/mp4"
        else:
            return JSONResponse({"ok": False, "error": "عملية غير معروفة."}, status_code=400)
 
        with open(tmp_out, "rb") as f:
            result_bytes = f.read()
        return Response(content=result_bytes, media_type=media_type)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    finally:
        for p in [tmp_in, tmp_out]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
 
 
# ---------- تقديم الواجهة (الملفات الثابتة) ----------
 
app.mount("/static", StaticFiles(directory="static"), name="static")
 
 
@app.get("/")
async def index():
    return FileResponse("static/index.html")
