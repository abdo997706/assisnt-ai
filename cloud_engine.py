import os
import random
import time
import json
import google.generativeai as genai
import requests

# 1. الدالة المطورة لـ Gemini و Grok بنظام التدوير والاحتياط
def generate_gemini_response(user_message, chat_history=None, system_prompt=None, model="gemini-1.5-flash", image=None):
    keys = [
        os.environ.get("GEMINI_API_KEY"),
        os.environ.get("GEMINI_API_KEY_2"),
        os.environ.get("GEMINI_API_KEY_3")
    ]
    valid_keys = [k for k in keys if k]
    
    if valid_keys:
        for attempt in range(len(valid_keys)):
            try:
                selected_key = random.choice(valid_keys)
                genai.configure(api_key=selected_key)
                gemini_model = genai.GenerativeModel(model)
                
                if image:
                    response = gemini_model.generate_content([user_message, image])
                else:
                    response = gemini_model.generate_content(user_message)
                return response.text
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    time.sleep(1)
                    continue
                break

    grok_key = os.environ.get("GROK_API_KEY")
    if grok_key:
        try:
            headers = {
                "Authorization": f"Bearer {grok_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "grok-4-fast-non-reasoning",
                "messages": [{"role": "user", "content": user_message}]
            }
            res = requests.post("https://x.ai", json=data, headers=headers)
            if res.status_code == 200:
                return res.json()["choices"]["message"]["content"]
        except:
            pass

    return "السيرفرات مشغولة حالياً بالكامل، يرجى إعادة إرسال الرسالة."

# 2. الدالة الاحتياطية المفقودة لقراءة وتحليل محتوى الملفات المرفوعة
def process_file_content(file_path, file_extension):
    try:
        if file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        elif file_extension == '.pdf':
            import pypdf
            reader = pypdf.PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        elif file_extension in ['.docx', '.doc']:
            import docx
            doc = docx.Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        return f"خطأ أثناء قراءة الملف: {str(e)}"
    return "امتداد ملف غير مدعوم."
 يرجى إرسال الرسالة مرة أخرى بعد لحظات."
