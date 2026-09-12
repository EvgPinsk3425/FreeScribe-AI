# F1 Whisper Typing — SEO и тексты для продвижения

Двуязычные материалы: **voice typing**, **offline whisper**, **голосовой ввод**, **диктовка текста**.  
Репозиторий: https://github.com/EvgPinsk3425/F1WhisperTyping  
Exe: https://github.com/EvgPinsk3425/F1WhisperTyping/releases/tag/v2.0

---

## Русский — полное описание (SEO)

### Заголовок

Бесплатный офлайн голосовой ввод для Windows и macOS: диктовка текста через Whisper без подписки и без GPU

### Лид

**F1 Whisper Typing** — это программа **голосового ввода** и **диктовки текста**. Вы нажимаете горячую клавишу, говорите в микрофон, и распознанная фраза вставляется в **активное окно**: блокнот, браузер, мессенджер, Word, почту, редактор кода. Распознавание — **офлайн Whisper** (faster-whisper) или GigaAM Сбера на обычном процессоре. **Облачная подписка не нужна.** **Скрытых платежей нет.** **Мощная видеокарта (GPU) не нужна.**

Ищите в GitHub: *голосовой ввод*, *диктовка текста*, *offline whisper*, *voice typing*, *speech to text*, *офлайн распознавание речи*.

### Возможности (полный список)

1. **Офлайн-распознавание речи через Whisper**  
   Модель лежит на диске. После скачивания интернет для диктовки не обязателен. Голос не отправляется в облако Microsoft/Google в локальном режиме.

2. **Нет облачных подписок и скрытых платежей**  
   Лицензия MIT, исходники открыты, готовый Windows `.exe` в Releases. Нет trial, нет «pro навсегда за оплату».

3. **Работа без мощной GPU**  
   CPU, int8. Подходит офисный ПК и ноутбук без NVIDIA.

4. **Кастомные горячие клавиши**  
   По умолчанию Ctrl+F8. Можно задать F1–F12, Ctrl+Пробел, правый Ctrl или свою комбинацию. Режим **удержания** (push-to-talk) или **переключатель** (нажал — запись, нажал — стоп).

5. **Автоматическая вставка в любые активные окна**  
   Буфер обмена + Ctrl+V (Windows) / Cmd+V (macOS). Работает в блокноте, Chrome/Edge/Firefox, Telegram Desktop, WhatsApp Web, Slack, Word, Excel (ячейка), VS Code, Cursor, почте.

6. **Первый запуск с автоскачиванием моделей**  
   Если модели нет в кэше, приложение само качает Whisper turbo (~1.6 ГБ) или small (~500 МБ) при нехватке места. В настройках можно скачать **GigaAM Сбера (~250 МБ)** — удобнее для русского **голосового ввода**.

7. **Каталог моделей**  
   Не произвольная ссылка, а список шаблонов: Whisper turbo / small / base / medium / large-v3 и две GigaAM. Качается только выбранная. Кнопка «Скачать выбранную», затем «Сохранить».

8. **Опциональный Groq**  
   Облако по желанию, не условие работы. Локальный **offline whisper** остаётся основным путём.

### Установка и первый запуск

**Windows, без Python**

1. Откройте [Releases](https://github.com/EvgPinsk3425/F1WhisperTyping/releases/tag/v2.0).
2. Скачайте `F1WhisperTyping.exe`.
3. Запустите. Иконка — в трее возле часов.
4. Дождитесь автоскачивания модели (или выберите GigaAM в Настройках).
5. Поставьте курсор в блокнот или чат, **Ctrl+F8**, диктуйте, **Ctrl+F8**.

**Windows, из исходников**

```powershell
git clone https://github.com/EvgPinsk3425/F1WhisperTyping.git
cd F1WhisperTyping
py -3.13 -m pip install -r requirements.txt
py -3.13 main.py
```

**macOS**

```bash
git clone https://github.com/EvgPinsk3425/F1WhisperTyping.git
cd F1WhisperTyping
./start.command
```

Разрешите микрофон и Универсальный доступ.

### Для кого

Программисты (диктовка в IDE), авторы, менеджеры в мессенджерах, те, кому нужен **приватный голосовой ввод** без облака и без покупки Dragon.

### Ключевые слова (RU)

голосовой ввод, диктовка текста, офлайн распознавание речи, whisper офлайн, голосовой набор windows, диктовка в telegram, речь в текст, бесплатный голосовой ввод, без видеокарты, push to talk

---

## English — full SEO description

### Title

Free offline voice typing for Windows and macOS — Whisper dictation, no subscription, no GPU

### Lead

**F1 Whisper Typing** is **offline voice typing** and **speech-to-text dictation**. Press a **custom hotkey**, speak, and the transcript is pasted into the **active window**: Notepad, browser, messengers, Word, email, IDE. Engine: **offline Whisper** (faster-whisper) or Sber GigaAM on CPU. **No cloud subscription. No hidden fees. No powerful GPU.**

GitHub search phrases: *voice typing*, *offline whisper*, *speech to text*, *dictation*, *push to talk*, *local ASR*.

### Feature list

1. **Offline speech recognition via Whisper** — after the first model download, dictation can work without sending audio to a vendor cloud.
2. **No cloud subscriptions or hidden payments** — MIT, public source, free Windows exe.
3. **Runs without a dedicated GPU** — CPU int8 on a normal laptop.
4. **Custom global hotkeys** — Ctrl+F8 default; F-keys, Ctrl+Space, right Ctrl, or a captured combo; hold or toggle.
5. **Auto-paste into any focused app** — Notepad, browsers, Telegram, Slack, Word, editors via clipboard paste.
6. **First-run auto-download** — turbo (~1.6 GB) or small (~500 MB) if disk is tight; optional GigaAM (~250 MB) for Russian.
7. **Model catalog** — pick, download, save. Only the selected model is fetched.
8. **Optional Groq** — cloud speed if you want it; not required.

### Install and first launch

Windows exe: download from [v2.0 Release](https://github.com/EvgPinsk3425/F1WhisperTyping/releases/tag/v2.0), run, wait for the model, then Ctrl+F8 in any text field.

From source: `git clone https://github.com/EvgPinsk3425/F1WhisperTyping.git` then `start.bat` (Windows) or `./start.command` (macOS). On Mac grant Microphone and Accessibility.

### Keywords (EN)

voice typing, offline whisper, speech to text, dictation software, voice to text windows, local whisper, push to talk dictation, no gpu speech recognition, free voice typing, offline asr

---

## GitHub About и Topics

**About:** `Free offline voice typing. Offline Whisper dictation, no GPU, no subscription. Windows + macOS. Голосовой ввод и диктовка текста.`

**Topics** (Settings → Topics):

```
voice-typing
offline-whisper
speech-to-text
dictation
голосовой-ввод
диктовка-текста
whisper
faster-whisper
push-to-talk
windows
macos
offline
russian
open-source
productivity
```

---

## Release notes (v2.0)

```
F1 Whisper Typing v2.0 — offline voice typing for Windows and macOS

• Hotkey → speak → paste into Notepad, browser, messengers
• Offline Whisper on CPU, no GPU, no subscription
• Custom hotkeys, push-to-talk or toggle
• First launch auto-downloads the speech model
• GigaAM (Sber) in Settings for compact Russian dictation
• Download F1WhisperTyping.exe below (Windows)
• macOS: clone the repo and run start.command
```

---

## Habr

**Заголовок:** Бесплатный офлайн голосовой ввод на Whisper: диктовка текста в любое окно без GPU и без подписки

Собрал **F1 Whisper Typing** — **голосовой ввод** и **диктовка текста** для Windows и Mac. Офлайн **Whisper**, без облачной подписки и без видеокарты. Ctrl+F8 — сказал — текст в блокноте, браузере или Telegram. Первый запуск сам качает модель. Исходники и exe: https://github.com/EvgPinsk3425/F1WhisperTyping

---

## Reddit

**Title:** [Free] Offline voice typing for Windows/macOS — Whisper dictation, no GPU, no subscription

**Body:** F1 Whisper Typing is offline voice typing: hotkey → speak → paste into any app. Local Whisper/GigaAM on CPU. Custom hotkeys. First run downloads the model. MIT. https://github.com/EvgPinsk3425/F1WhisperTyping

---

## Telegram

🎤 **F1 Whisper Typing** — бесплатный **голосовой ввод** и **диктовка текста**. Офлайн Whisper, без подписки, без GPU. Ctrl+F8 → речь → вставка в любое окно. https://github.com/EvgPinsk3425/F1WhisperTyping

---

## Product Hunt (EN)

**Tagline:** Offline voice typing with Whisper — no GPU, no subscription.

**Description:** Press a hotkey, speak, and text lands in Notepad, the browser, or messengers. Offline Whisper on CPU. Custom hotkeys. Auto model download on first launch. Open source (MIT).

---

## Чеклист

- [x] Публичный репозиторий
- [x] Release с exe (v2.0)
- [ ] Topics добавлены в настройках репозитория (список выше)
- [ ] About заполнен
- [ ] Пост на Habr / Reddit / Telegram
