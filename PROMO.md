# Тексты для продвижения F1 Whisper Typing

Готовые блоки — копируйте и подставьте ссылку на репозиторий после публикации на GitHub.

---

## Release v1.0.0 (GitHub → Releases → New release)

**Tag:** `v1.0.0`  
**Title:** F1 Whisper Typing v1.0.0 — офлайн голосовой набор для Windows

**Описание:**

```
🎤 F1 Whisper Typing — бесплатный офлайн голосовой набор для Windows 10/11.

• Нажали Ctrl+F8 → сказали → текст вставился в любое окно
• Работает без интернета (faster-whisper на CPU)
• Русский язык, push-to-talk / toggle
• Не нужна видеокарта
• Опционально Groq API для скорости

📥 Скачайте F1WhisperTyping.exe ниже — Python не нужен.

Первый запуск скачает модель Whisper (~500 МБ). Иконка — в трее возле часов.

Настройки: правый клик по иконке → Настройки.
```

**Прикрепить файл:** `dist/F1WhisperTyping.exe`

---

## Habr (статья или пост)

**Заголовок:** Сделал бесплатный аналог WhisperTyping: офлайн голосовой набор для Windows на Whisper

**Текст:**

Привет, Habr!

Долго пользовался разными программами для голосового ввода — Windows «Голосовой ввод», платные решения, WhisperTyping. В итоге собрал свой вариант: **F1 Whisper Typing**.

**Что умеет:**
- Говоришь по горячей клавише (Ctrl+F8) — текст сразу вставляется в активное окно: Word, Telegram, браузер, IDE
- Полностью **офлайн** — faster-whisper, модель крутится на CPU, GPU не нужен
- **Русский язык** из коробки
- Режим **удержания** (push-to-talk) или **переключатель**
- Вставка через буфер обмена — стабильнее, чем эмуляция клавиш
- Open source, MIT, есть готовый `.exe`

**Чем отличается от WhisperTyping:** по сути тот же класс задач, но с готовым exe, русским интерфейсом настроек, опциональным Groq API и моделью turbo по умолчанию.

**Чем отличается от Windows Speech:** не отправляет аудио в облако Microsoft, работает в любом приложении одинаково.

Скачать и исходники: [ССЫЛКА_НА_GITHUB]

Буду рад звёздам ⭐ и issue с идеями. Если кому-то полезно — попробуйте и напишите, что улучшить.

---

## Reddit (r/software, r/Windows10, r/opensource)

**Title:** [Free / Open Source] Offline voice typing for Windows — push-to-talk, Russian, no GPU (Whisper-based)

**Body:**

I built **F1 Whisper Typing** — a free, offline voice dictation tool for Windows 10/11.

**How it works:** press a hotkey (Ctrl+F8) → speak → text is pasted into whatever window is focused.

**Features:**
- Fully offline (faster-whisper on CPU, int8)
- Push-to-talk or toggle mode
- Works in any app (browser, Word, Telegram, IDE…)
- Reliable clipboard-based paste
- System tray, configurable hotkeys
- Optional Groq API if you want cloud speed
- MIT license, ready `.exe` in Releases

Similar to WhisperTyping but with a pre-built exe and Russian-first UX.

Download: [GITHUB_LINK]

Feedback and stars welcome!

---

## Telegram (короткий пост)

🎤 **F1 Whisper Typing** — бесплатный офлайн голосовой набор для Windows.

Ctrl+F8 → говоришь → текст в Word / Telegram / браузере. Без облака, без подписки, русский язык, работает на обычном CPU.

Open source, готовый exe: [ССЫЛКА]

---

## Product Hunt (англ.)

**Tagline:** Offline voice typing for Windows — press, speak, paste.

**Description:**

F1 Whisper Typing turns your microphone into a universal dictation tool. Press Ctrl+F8, speak, and text appears in any app — Word, Slack, browser, IDE.

Unlike cloud dictation, everything runs locally with Whisper. No subscription, no GPU required. Open source (MIT).

---

## Чеклист перед публикацией

- [ ] Репозиторий на GitHub (public)
- [ ] Topics добавлены (см. README)
- [ ] Release v1.0.0 с `.exe`
- [ ] GIF-демо в README (10 сек: нажал → сказал → текст появился)
- [ ] Заменить `YOUR_USERNAME` и `ССЫЛКА` на реальные URL
- [ ] Пост на Habr или Reddit
- [ ] Попросить 5–10 знакомых поставить ⭐
