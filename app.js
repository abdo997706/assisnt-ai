let currentUser = null;
let currentChatId = "الشات الافتراضي";
let pendingAttachmentImageUrl = null;
let remainingSeconds = 0;
let usageInterval = null;

// ---------- تبديل تابات تسجيل الدخول ----------
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab + "-tab").classList.add("active");
  });
});

// ---------- تسجيل الدخول ----------
async function login() {
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value.trim();
  const errorEl = document.getElementById("login-error");
  errorEl.textContent = "";

  if (!username || !password) { errorEl.textContent = "املأ كل الحقول."; return; }

  const res = await fetch("/api/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = await res.json();

  if (data.ok) {
    currentUser = username;
    await checkUsageAndProceed();
  } else {
    errorEl.textContent = data.error || "حصل خطأ.";
  }
}

async function signup() {
  const username = document.getElementById("signup-username").value.trim();
  const password = document.getElementById("signup-password").value.trim();
  const question = document.getElementById("signup-question").value.trim();
  const answer = document.getElementById("signup-answer").value.trim();
  const errorEl = document.getElementById("signup-error");
  errorEl.textContent = "";

  const res = await fetch("/api/signup", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, question, answer }),
  });
  const data = await res.json();

  if (data.ok) {
    alert("تم إنشاء الحساب! سجّل دخولك دلوقتي.");
    document.querySelector('[data-tab="login"]').click();
  } else {
    errorEl.textContent = data.error || "حصل خطأ.";
  }
}

async function fetchSecurityQuestion() {
  const username = document.getElementById("forgot-username").value.trim();
  const errorEl = document.getElementById("forgot-error");
  errorEl.textContent = "";

  const res = await fetch("/api/get_security_question", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username }),
  });
  const data = await res.json();

  if (data.ok) {
    document.getElementById("forgot-question").textContent = "❓ " + data.question;
    document.querySelectorAll("#forgot-tab .hidden-field").forEach(el => el.classList.remove("hidden-field"));
  } else {
    errorEl.textContent = data.error || "حصل خطأ.";
  }
}

async function resetPassword() {
  const username = document.getElementById("forgot-username").value.trim();
  const answer = document.getElementById("forgot-answer").value.trim();
  const newPassword = document.getElementById("forgot-newpass").value.trim();
  const errorEl = document.getElementById("forgot-error");
  errorEl.textContent = "";

  const res = await fetch("/api/reset_password", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, answer, new_password: newPassword }),
  });
  const data = await res.json();

  if (data.ok) {
    alert("تم تغيير كلمة المرور بنجاح! سجّل دخولك دلوقتي.");
    document.querySelector('[data-tab="login"]').click();
  } else {
    errorEl.textContent = data.error || "حصل خطأ.";
  }
}

function logout() {
  if (usageInterval) clearInterval(usageInterval);
  currentUser = null;
  document.getElementById("chat-screen").classList.add("hidden");
  document.getElementById("lock-screen").classList.add("hidden");
  document.getElementById("auth-screen").classList.remove("hidden");
}

// ---------- نظام الوقت المسموح ----------
async function checkUsageAndProceed() {
  const res = await fetch(`/api/usage/${currentUser}`);
  const data = await res.json();

  if (data.locked) {
    showLockScreen(data.remaining_lock_seconds);
  } else {
    remainingSeconds = data.remaining_free_seconds;
    await showChatScreen();
    startUsageCountdown(data.is_vip);
  }
}

function showLockScreen(remainingLockSeconds) {
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("chat-screen").classList.add("hidden");
  document.getElementById("lock-screen").classList.remove("hidden");
  const h = Math.floor(remainingLockSeconds / 3600);
  const m = Math.floor((remainingLockSeconds % 3600) / 60);
  document.getElementById("lock-message").textContent =
    `استخدمت وقتك المتاح بالكامل. تقدر تستخدم البرنامج تاني بعد ${h} ساعة و${m} دقيقة، أو فعّل كود ساعات إضافية دلوقتي.`;
}

async function redeemCode() {
  const code = document.getElementById("vip-code-input").value.trim();
  const errorEl = document.getElementById("lock-error");
  errorEl.textContent = "";

  const res = await fetch("/api/redeem_code", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: currentUser, code }),
  });
  const data = await res.json();

  if (data.ok) {
    alert(`🎉 تم تفعيل الكود! اتضافلك ${data.hours_added} ساعة.`);
    await checkUsageAndProceed();
  } else {
    errorEl.textContent = data.error || "حصل خطأ.";
  }
}

function startUsageCountdown(isVip) {
  const el = document.getElementById("remaining-time");
  if (usageInterval) clearInterval(usageInterval);

  if (isVip) { el.textContent = "👑 حساب VIP - استخدام غير محدود"; return; }

  const update = () => {
    const h = Math.floor(remainingSeconds / 3600);
    const m = Math.floor((remainingSeconds % 3600) / 60);
    el.textContent = `⏳ باقي ${h}س ${m}د من وقتك المتاح`;
  };
  update();

  usageInterval = setInterval(() => {
    remainingSeconds -= 1;
    if (remainingSeconds <= 0) { clearInterval(usageInterval); checkUsageAndProceed(); return; }
    update();
  }, 1000);
}

// ---------- شاشة الشات ----------
async function showChatScreen() {
  document.getElementById("auth-screen").classList.add("hidden");
  document.getElementById("lock-screen").classList.add("hidden");
  document.getElementById("chat-screen").classList.remove("hidden");
  await loadChats();
}

async function loadChats() {
  const res = await fetch(`/api/chats/${currentUser}`);
  const chats = await res.json();
  renderChatList(chats);
  const firstChat = Object.keys(chats)[0];
  currentChatId = currentChatId in chats ? currentChatId : firstChat;
  renderMessages(chats[currentChatId] || []);
}

function renderChatList(chats) {
  const listEl = document.getElementById("chat-list");
  listEl.innerHTML = "";
  Object.keys(chats).forEach(chatName => {
    const wrapper = document.createElement("div");
    wrapper.className = "chat-list-item" + (chatName === currentChatId ? " active" : "");

    const nameSpan = document.createElement("span");
    nameSpan.className = "chat-name-text";
    nameSpan.textContent = chatName;
    nameSpan.onclick = () => {
      currentChatId = chatName;
      renderChatList(chats);
      renderMessages(chats[chatName]);
    };

    const actions = document.createElement("span");
    actions.className = "chat-actions";

    const renameBtn = document.createElement("button");
    renameBtn.className = "chat-action-btn";
    renameBtn.textContent = "✏️";
    renameBtn.onclick = (e) => { e.stopPropagation(); renameChat(chatName); };

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "chat-action-btn";
    deleteBtn.textContent = "🗑️";
    deleteBtn.onclick = (e) => { e.stopPropagation(); deleteChat(chatName); };

    actions.appendChild(renameBtn);
    actions.appendChild(deleteBtn);
    wrapper.appendChild(nameSpan);
    wrapper.appendChild(actions);
    listEl.appendChild(wrapper);
  });
}

async function deleteChat(chatName) {
  if (!confirm(`متأكد عايز تمسح شات "${chatName}"؟`)) return;
  const res = await fetch("/api/delete_chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: currentUser, chat_name: chatName }),
  });
  const data = await res.json();
  if (data.ok) {
    if (currentChatId === chatName) currentChatId = Object.keys(data.chats)[0];
    renderChatList(data.chats);
    renderMessages(data.chats[currentChatId]);
  } else {
    alert(data.error || "حصل خطأ.");
  }
}

async function renameChat(chatName) {
  const newName = prompt("اكتب الاسم الجديد:", chatName);
  if (!newName || newName.trim() === "" || newName === chatName) return;
  const res = await fetch("/api/rename_chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: currentUser, old_name: chatName, new_name: newName.trim() }),
  });
  const data = await res.json();
  if (data.ok) {
    if (currentChatId === chatName) currentChatId = newName.trim();
    renderChatList(data.chats);
    renderMessages(data.chats[currentChatId]);
  } else {
    alert(data.error || "حصل خطأ.");
  }
}

async function createNewChat() {
  const nameInput = document.getElementById("new-chat-name");
  const name = nameInput.value.trim();
  if (!name) return;

  const res = await fetch("/api/new_chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: currentUser, chat_name: name }),
  });
  const chats = await res.json();
  currentChatId = name;
  nameInput.value = "";
  renderChatList(chats);
  renderMessages(chats[name]);
}

// ---------- عرض الرسايل ----------
function renderMessages(messages) {
  const container = document.getElementById("messages");
  container.innerHTML = "";
  messages.forEach(msg => appendMessage(msg.role, msg.content));
  container.scrollTop = container.scrollHeight;
}

function appendMessage(role, content, imageUrl) {
  const container = document.getElementById("messages");
  const row = document.createElement("div");
  row.className = "msg-row " + role;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "🧑" : "🤖";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (imageUrl) {
    const img = document.createElement("img");
    img.src = imageUrl;
    img.className = "message-image";
    bubble.appendChild(img);
  }

  const textEl = document.createElement("div");
  textEl.className = "bubble-text";
  textEl.textContent = content;
  bubble.appendChild(textEl);

  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

// ---------- إرسال رسالة ----------
async function sendMessage() {
  const input = document.getElementById("message-input");
  const text = input.value.trim();
  if (!text) return;

  appendMessage("user", text, pendingAttachmentImageUrl);
  input.value = "";
  pendingAttachmentImageUrl = null;
  clearAttachmentPreview();

  const thinkingBubble = appendMessage("assistant", "🤔 بيفكر في الرد...");
  thinkingBubble.classList.add("thinking");

  const res = await fetch("/api/chat", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: currentUser, chat_id: currentChatId, message: text }),
  });

  if (res.status === 403) {
    const errData = await res.json();
    showLockScreen(errData.remaining_lock_seconds || 0);
    return;
  }

  const data = await res.json();
  thinkingBubble.querySelector(".bubble-text").textContent = data.reply;
  thinkingBubble.classList.remove("thinking");
}

// ---------- قائمة "+" ----------
function togglePlusMenu() {
  document.getElementById("plus-menu").classList.toggle("hidden");
  document.getElementById("plus-btn").classList.toggle("open");
}

document.addEventListener("click", (e) => {
  const menu = document.getElementById("plus-menu");
  const btn = document.getElementById("plus-btn");
  if (!menu.contains(e.target) && e.target !== btn && !menu.classList.contains("hidden")) {
    menu.classList.add("hidden");
    btn.classList.remove("open");
  }
});

// ---------- رفع ملفات/صور للشات ----------
async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  await uploadFile(file);
  document.getElementById("plus-menu").classList.add("hidden");
  document.getElementById("plus-btn").classList.remove("open");
}

async function uploadFile(file) {
  const isImage = file.type && file.type.startsWith("image/");

  if (isImage) {
    pendingAttachmentImageUrl = URL.createObjectURL(file);
    showAttachmentPreview(file, "image");
  } else {
    pendingAttachmentImageUrl = null;
    showAttachmentPreview(file, "document", "📖 بيقرا الملف...");
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("username", currentUser);

  const res = await fetch("/api/upload", { method: "POST", body: formData });
  const data = await res.json();

  if (!data.ok) {
    clearAttachmentPreview();
    pendingAttachmentImageUrl = null;
    appendMessage("assistant", `❌ ${data.error || "حصل خطأ في رفع الملف."}`);
    return;
  }

  if (!isImage) {
    showAttachmentPreview(file, "document", `📄 ${data.filename} (${data.chars} حرف)`);
  }
}

function showAttachmentPreview(file, type, label) {
  const preview = document.getElementById("attachment-preview");
  preview.classList.remove("hidden");

  if (type === "image") {
    preview.innerHTML = `
      <img src="${pendingAttachmentImageUrl}" class="preview-thumb">
      <button class="preview-remove-btn" onclick="clearAttachmentPreview()">✕</button>
    `;
  } else {
    preview.innerHTML = `
      <div class="preview-file-chip">📄 ${label || file.name}</div>
      <button class="preview-remove-btn" onclick="clearAttachmentPreview()">✕</button>
    `;
  }
}

function clearAttachmentPreview() {
  pendingAttachmentImageUrl = null;
  const preview = document.getElementById("attachment-preview");
  preview.innerHTML = "";
  preview.classList.add("hidden");
}

// ---------- لصق صورة مباشرة (Ctrl+V) ----------
document.getElementById("message-input").addEventListener("paste", async (e) => {
  const items = e.clipboardData ? e.clipboardData.items : [];
  for (const item of items) {
    if (item.type && item.type.startsWith("image/")) {
      e.preventDefault();
      const blob = item.getAsFile();
      await uploadFile(new File([blob], "pasted_image.png", { type: blob.type }));
    }
  }
});

// ---------- نوافذ Modal ----------
function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
  document.getElementById("plus-menu").classList.add("hidden");
  document.getElementById("plus-btn").classList.remove("open");
}
function closeModal(id) {
  document.getElementById(id).classList.add("hidden");
}

// ---------- محرر الصور ----------
document.getElementById("edit-image-file").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  const img = document.getElementById("edit-image-preview");
  img.src = url;
  img.style.display = "block";
});

function updateImageEditorFields() {
  const op = document.getElementById("edit-image-operation").value;
  const container = document.getElementById("image-editor-fields");
  container.innerHTML = "";
  if (op === "resize") {
    container.innerHTML = `
      <div class="editor-field-row">
        <input type="number" id="f-width" placeholder="العرض">
        <input type="number" id="f-height" placeholder="الطول">
      </div>`;
  } else if (op === "crop") {
    container.innerHTML = `
      <div class="editor-field-row">
        <input type="number" id="f-left" placeholder="من اليسار">
        <input type="number" id="f-top" placeholder="من فوق">
      </div>
      <div class="editor-field-row">
        <input type="number" id="f-right" placeholder="لحد اليمين">
        <input type="number" id="f-bottom" placeholder="لحد تحت">
      </div>`;
  } else if (op === "rotate") {
    container.innerHTML = `<input type="number" id="f-angle" placeholder="زاوية الدوران" value="90">`;
  } else if (op === "brightness") {
    container.innerHTML = `<input type="number" id="f-factor" placeholder="درجة (1 = بدون تغيير)" value="1.3" step="0.1">`;
  } else if (op === "flip") {
    container.innerHTML = `
      <select id="f-flip-mode">
        <option value="horizontal">أفقي</option>
        <option value="vertical">رأسي</option>
      </select>`;
  }
}

async function applyImageEdit() {
  const fileInput = document.getElementById("edit-image-file");
  const file = fileInput.files[0];
  if (!file) { alert("ارفع صورة الأول."); return; }

  const op = document.getElementById("edit-image-operation").value;
  const formData = new FormData();
  formData.append("file", file);
  formData.append("operation", op);

  if (op === "resize") {
    formData.append("width", document.getElementById("f-width").value);
    formData.append("height", document.getElementById("f-height").value);
  } else if (op === "crop") {
    formData.append("left", document.getElementById("f-left").value);
    formData.append("top", document.getElementById("f-top").value);
    formData.append("right", document.getElementById("f-right").value);
    formData.append("bottom", document.getElementById("f-bottom").value);
  } else if (op === "rotate") {
    formData.append("angle", document.getElementById("f-angle").value);
  } else if (op === "brightness") {
    formData.append("factor", document.getElementById("f-factor").value);
  } else if (op === "flip") {
    formData.append("flip_mode", document.getElementById("f-flip-mode").value);
  }

  const resultDiv = document.getElementById("image-editor-result");
  resultDiv.innerHTML = "⏳ بيعالج...";

  const res = await fetch("/api/edit_image", { method: "POST", body: formData });
  if (!res.ok) {
    const err = await res.json();
    resultDiv.innerHTML = `❌ ${err.error || "حصل خطأ"}`;
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  resultDiv.innerHTML = `
    <img src="${url}" class="editor-result-media">
    <a href="${url}" download="edited_image.png" class="editor-download-link">⬇️ تحميل</a>
  `;
}

// ---------- محرر الفيديو ----------
function updateVideoEditorFields() {
  const op = document.getElementById("edit-video-operation").value;
  const container = document.getElementById("video-editor-fields");
  container.innerHTML = "";
  if (op === "trim") {
    container.innerHTML = `
      <div class="editor-field-row">
        <input type="number" id="v-start" placeholder="البداية (ثانية)" value="0">
        <input type="number" id="v-end" placeholder="النهاية (ثانية)" value="5">
      </div>`;
  } else if (op === "resize") {
    container.innerHTML = `
      <div class="editor-field-row">
        <input type="number" id="v-width" placeholder="العرض" value="640">
        <input type="number" id="v-height" placeholder="الطول" value="360">
      </div>`;
  }
}

async function applyVideoEdit() {
  const fileInput = document.getElementById("edit-video-file");
  const file = fileInput.files[0];
  if (!file) { alert("ارفع فيديو الأول."); return; }

  const op = document.getElementById("edit-video-operation").value;
  const formData = new FormData();
  formData.append("file", file);
  formData.append("operation", op);

  if (op === "trim") {
    formData.append("start", document.getElementById("v-start").value);
    formData.append("end", document.getElementById("v-end").value);
  } else if (op === "resize") {
    formData.append("width", document.getElementById("v-width").value);
    formData.append("height", document.getElementById("v-height").value);
  }

  const resultDiv = document.getElementById("video-editor-result");
  resultDiv.innerHTML = "⏳ بيعالج... (ممكن ياخد وقت أول مرة)";

  const res = await fetch("/api/edit_video", { method: "POST", body: formData });
  if (!res.ok) {
    const err = await res.json();
    resultDiv.innerHTML = `❌ ${err.error || "حصل خطأ"}`;
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const isAudio = op === "extract_audio";
  resultDiv.innerHTML = isAudio
    ? `<audio controls src="${url}" style="width:100%; margin-top:8px;"></audio>
       <a href="${url}" download="extracted_audio.mp3" class="editor-download-link">⬇️ تحميل</a>`
    : `<video controls src="${url}" class="editor-result-media"></video>
       <a href="${url}" download="edited_video.mp4" class="editor-download-link">⬇️ تحميل</a>`;
}

// تهيئة الحقول الافتراضية عند التحميل
updateImageEditorFields();
updateVideoEditorFields();
