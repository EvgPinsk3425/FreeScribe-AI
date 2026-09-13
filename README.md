# FreeScribe-AI

**Free offline voice typing / бесплатный офлайн голосовой ввод** for Windows and macOS.  
Press a hotkey → speak → text is pasted into Notepad, the browser, messengers, Word, or any focused window.

[English](#english) · [Русский](#русский)

![Windows](https://img.shields.io/badge/Windows-10%2F11-blue)
![macOS](https://img.shields.io/badge/macOS-12+-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Offline](https://img.shields.io/badge/offline-whisper-brightgreen)
![No GPU](https://img.shields.io/badge/GPU-not%20required-lightgrey)

**Repo:** [github.com/EvgPinsk3425/FreeScribe-AI](https://github.com/EvgPinsk3425/FreeScribe-AI)  
**Windows exe:** [Releases · v2.3](https://github.com/EvgPinsk3425/FreeScribe-AI/releases/tag/v2.3)

Open-source **offline Whisper** dictation. No cloud subscription, no hidden fees, no NVIDIA GPU. Keywords: *voice typing, offline whisper, голосовой ввод, диктовка текста, speech to text, push-to-talk*.

---

## Русский

### Что это

**FreeScribe-AI** — программа для **диктовки текста** и **голосового ввода** на компьютере. Распознавание речи идёт **офлайн** через **Whisper** (faster-whisper) или модель **GigaAM Сбера**. Аудио не обязано уходить в облако Microsoft, Google или платный сервис.

Аналог [WhisperTyping](https://github.com/savoirfairelinux/whisper-typing): горячая клавиша, запись с микрофона, вставка в **активное окно**.

| | FreeScribe-AI | Windows «Голосовой ввод» | Платные диктовки |
|---|---|---|---|
| Цена | Бесплатно, MIT | Встроено | Подписка |
| Офлайн | Да (local Whisper) | Облако | Зависит |
| Скрытые платежи | Нет | — | Часто есть |
| GPU | Не нужен (CPU int8) | — | Часто нужен |
| Куда вставляет | Блокнот, браузер, мессенджеры, IDE | Не везде | Обычно да |

### Возможности

- **Офлайн-распознавание речи через Whisper** — модель на вашем диске, интернет нужен только чтобы один раз скачать модель.
- **Нет облачных подписок и скрытых платежей** — MIT, без аккаунта и пробного периода.
- **Работа без мощной видеокарты (GPU)** — CPU, квантование int8. Подойдёт обычный ноутбук.
- **Кастомные горячие клавиши** — Ctrl+F8 по умолчанию; F1–F12, Ctrl+Пробел, правый Ctrl или своя комбинация. Режим удержания (push-to-talk) или переключатель.
- **Автоматическая вставка текста** в любое активное окно: блокнот, браузер, Telegram, WhatsApp Web, Word, почта, IDE — через буфер и Ctrl+V / Cmd+V.
- Каталог моделей в настройках: Whisper turbo / small / large и **GigaAM** (~250 МБ) для русского.
- Опционально Groq API, если нужна облачная скорость. Локальный режим от этого не зависит.
- **Всплывающие подсказки** у иконки и **звуки старта/стопа записи** — включаются в настройках.

### Установка Windows (exe)

1. Скачайте **FreeScribe-AI.exe** из [Releases](https://github.com/EvgPinsk3425/FreeScribe-AI/releases).
2. Запустите файл. Иконка микрофона — в системном трее (иногда в ▲ скрытых значках).
3. Откройте поле ввода, нажмите **Ctrl+F8**, говорите, нажмите ещё раз.
4. Текст вставится в активное окно.

**Первый запуск и автоскачивание моделей.** Если модели ещё нет, программа сама начнёт загрузку (turbo ~1.6 ГБ или small ~500 МБ, если мало места). Не закрывайте приложение, пока модель не скачается. Для русской диктовки удобнее GigaAM: трей → Настройки → Модели → Сбер → **Скачать выбранную** → **Сохранить**.

### Установка из исходников (Windows)

```powershell
git clone https://github.com/EvgPinsk3425/FreeScribe-AI.git
cd FreeScribe-AI
py -3.13 -m pip install -r requirements.txt
py -3.13 main.py
```

Либо `start.bat`. Не используйте случайный `python` из PATH — может быть другой интерпретатор без пакетов.

### Установка macOS

```bash
git clone https://github.com/EvgPinsk3425/FreeScribe-AI.git
cd FreeScribe-AI
chmod +x start.command
./start.command
```

Разрешите **микрофон** и **Универсальный доступ (Accessibility)** — иначе не будет записи и вставки. Иконка — в строке меню.

### Модели

| Группа | Модель | Размер | Назначение |
|---|---|---|---|
| Whisper | turbo | ~1.6 ГБ | Быстрый offline whisper, по умолчанию |
| Whisper | small / base | 150–500 МБ | Мало места на диске |
| Сбер | GigaAM v3 RNN-T | ~250 МБ | Русский голосовой ввод, пунктуация |
| Сбер | GigaAM v3 CTC | ~250 МБ | Быстрее RNN-T |

Настройки → Модели → выбрать → **Скачать** → **Сохранить**. Качается только выбранная модель.

### Сборка exe

`build.bat` → `dist\FreeScribe-AI.exe`. GitHub Actions собирает exe по тегу `v*`.

### Требования

Windows 10/11 или macOS 12+, микрофон, 250 МБ–3 ГБ на диске под модель. Python 3.11+ только для запуска из исходников.

---

## English

### What it is

**FreeScribe-AI** is **free offline voice typing** and **speech-to-text dictation** for Windows and macOS. It uses **offline Whisper** (faster-whisper) or Sber **GigaAM** on your CPU. No Microsoft/Google cloud required for the local path. No subscription. No hidden fees. No dedicated GPU.

Workflow: custom hotkey → speak → the transcript is pasted into the **active window** (Notepad, browser, messengers, Word, IDE).

### Features

- **Offline speech recognition via Whisper** — voice stays on the PC after the model is downloaded.
- **No cloud subscriptions or hidden payments** — MIT license, no account.
- **No powerful GPU required** — CPU int8; works on a regular laptop.
- **Custom global hotkeys** — default Ctrl+F8; F-keys, Ctrl+Space, right Ctrl, or your own combo; hold (push-to-talk) or toggle.
- **Auto-insert into any focused app** — Notepad, Chrome/Edge, Telegram, Slack, email, editors — clipboard + Ctrl+V / Cmd+V.
- Model catalog: Whisper turbo/small/large and compact GigaAM (~250 MB) for Russian dictation.
- Optional Groq API for cloud speed; local dictation still works without it.
- Tray **toast tips** and **start/stop beeps** — toggles in Settings.

### Install (Windows exe)

1. Download **FreeScribe-AI.exe** from [Releases](https://github.com/EvgPinsk3425/FreeScribe-AI/releases).
2. Run it. A microphone icon appears in the system tray (check hidden icons).
3. Focus a text field, press **Ctrl+F8**, speak, press again.
4. Text is pasted automatically.

**First launch / auto-download.** If no model is cached, the app downloads one (turbo ~1.6 GB, or small ~500 MB if disk is low). Keep the app open until it finishes. For Russian, prefer GigaAM: tray → Settings → Models → download → Save.

### Install from source

**Windows**

```powershell
git clone https://github.com/EvgPinsk3425/FreeScribe-AI.git
cd FreeScribe-AI
py -3.13 -m pip install -r requirements.txt
py -3.13 main.py
```

**macOS**

```bash
git clone https://github.com/EvgPinsk3425/FreeScribe-AI.git
cd FreeScribe-AI
chmod +x start.command
./start.command
```

Allow **Microphone** and **Accessibility**. Menu-bar icon is top-right.

### Models

Same catalog as in the Russian table above. Download only what you select. First run auto-downloads if nothing is cached.

### Build

`build.bat` → `dist\FreeScribe-AI.exe`.

### Requirements

Windows 10/11 or macOS 12+, a microphone, 250 MB–3 GB disk for models. Python 3.11+ for source installs.

---

## GitHub topics

```
voice-typing, offline-whisper, speech-to-text, dictation, голосовой-ввод,
диктовка-текста, whisper, faster-whisper, push-to-talk, windows, macos,
offline, russian, open-source, productivity
```

**About:** `Free offline voice typing. Whisper dictation, no GPU, no subscription. Windows + macOS.`

Promotional copy: [PROMO.md](PROMO.md). License: MIT.
