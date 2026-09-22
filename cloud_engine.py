import os
import random
import time
import google.generativeai as genai
import requests

def generate_gemini_response(user_message, chat_history=None, system_prompt=None, model="gemini-1.5-flash", image=None):
    # 1. جمع كل مفاتيح جيميناي الثلاثة التي أضفناها في رايلواي داخل قائمة
    keys = [
        os.environ.get("GEMINI_API_KEY"),
        os.environ.get("GEMINI_API_KEY_2"),
        os.environ.get("GEMINI_API_KEY_3")
    ]
    # تصفية القائمة للتأكد من استبعاد أي مفتاح فارغ
    valid_keys = [k for k in keys if k]
    
    # 2. نظام التدوير العشوائي وإعادة المحاولة في حال وجود ضغط 503
    if valid_keys:
        for attempt in range(len(valid_keys)):
            try:
                selected_key = random.choice(valid_keys)
                genai.configure(api_key=selected_key)
                
                gemini_model = genai.GenerativeModel(model)
                
                # إرسال الرسالة لجوجل
                if chat_history:
                    chat = gemini_model.start_chat(history=[])
                    response = chat.send_message(user_message)
                else:
                    response = gemini_model.generate_content(user_message)
                
                return response.text
            except Exception as e:
                # إذا واجه هذا المفتاح ضغط 503، ينتظر ثانية ويحاول بمفتاح آخر عشوائي
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    time.sleep(1)
                    continue
                break

    # 3. نظام الاحتياط التلقائي (Fallback) - التحويل لجروك فوراً لو انهارت خوادم جوجل تماماً
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

    return "السيرفرات مشغولة حالياً بالكامل، يرجى إرسال الرسالة مرة أخرى بعد لحظات."
