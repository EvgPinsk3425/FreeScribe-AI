# F1 Whisper Typing

**Бесплатный офлайн голосовой набор для Windows и macOS.** Нажали горячую клавишу → сказали → текст вставился в любое окно. Без подписки, без облака, без GPU.

> Аналог [WhisperTyping](https://github.com/savoirfairelinux/whisper-typing) — open source, заточен под русский язык.

![Windows](https://img.shields.io/badge/Windows-10%2F11-blue)
![macOS](https://img.shields.io/badge/macOS-12+-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![Offline](https://img.shields.io/badge/offline-yes-brightgreen)

## Быстрый старт

### Windows (exe)

1. Скачайте **F1WhisperTyping.exe** из [Releases](../../releases).
2. Запустите — иконка микрофона появится в трее (иногда в скрытых значках ▲).
3. Откройте текстовое поле, нажмите **Ctrl+F8**, говорите, нажмите ещё раз.
4. Текст вставится сам.

При первом запуске программа сама скачает модель (turbo ~1.6 ГБ или small ~500 МБ). Для русского удобнее **GigaAM Сбера** (~250 МБ): трей → Настройки → Модели.

### macOS (из исходников)

Нужны Python 3.11+ и микрофон.

```bash
git clone https://github.com/YOUR_USERNAME/F1WhisperTyping.git
cd F1WhisperTyping
chmod +x start.command
./start.command
```

Или вручную:

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

На Mac разрешите:

- **Микрофон** — Системные настройки → Конфиденциальность и безопасность;
- **Универсальный доступ (Accessibility)** — для горячей клавиши и вставки текста.

Иконка — в строке меню справа вверху.

## Модели (каталог)

В настройках список готовых шаблонов. Скачивается только выбранная.

| Группа | Модель | Размер | Зачем |
|---|---|---|---|
| Whisper | turbo ★ | ~1.6 ГБ | быстро и точно, по умолчанию |
| Whisper | small / base | 150–500 МБ | если мало места |
| **Сбер** | **GigaAM v3 RNN-T ★** | **~250 МБ** | лучше на русском, с пунктуацией |
| Сбер | GigaAM v3 CTC | ~250 МБ | быстрее RNN-T |

Как скачать: Настройки → Модели → выбрать → **Скачать выбранную** → **Сохранить**.

Новая модель в каталог — ещё один словарь в `MODEL_CATALOG` (`settings.py`).

## Возможности

- Push-to-Talk или переключатель (по умолчанию Ctrl+F8)
- Офлайн: faster-whisper и GigaAM Сбера на CPU
- Вставка через буфер (Ctrl+V / Cmd+V)
- Трей / строка меню
- Опционально Groq API

## Установка из исходников (Windows)

```powershell
git clone https://github.com/YOUR_USERNAME/F1WhisperTyping.git
cd F1WhisperTyping
py -3.13 -m pip install -r requirements.txt
py -3.13 main.py
```

Либо двойной щелчок по `start.bat`. Не используйте голый `python`, если в PATH другой интерпретатор.

## Сборка exe (Windows)

```powershell
build.bat
```

Файл: `dist\F1WhisperTyping.exe`. CI собирает exe при теге `v*` (Actions → Build Windows exe).

## Требования

- Windows 10/11 или macOS 12+
- Микрофон
- Для исходников: Python 3.11+
- Место на диске под модель (250 МБ–3 ГБ)

## Лицензия

MIT — свободное использование и модификация.
