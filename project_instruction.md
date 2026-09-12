# F1 Whisper Typing — инструкция по проекту

Офлайн голосовой набор для Windows и macOS: горячая клавиша → речь → текст в активном окне.

## Запуск

- Windows: `start.bat` или `py -3.13 main.py`. Готовый exe: `dist\F1WhisperTyping.exe` / Releases.
- macOS: `./start.command` или `python3 main.py`. Разрешить микрофон и Универсальный доступ.

Не запускать через случайный `python` из PATH (может быть другой интерпретатор без пакетов).

## Модели

Каталог `MODEL_CATALOG` в `settings.py`. В окне настроек: выбрать → «Скачать» → «Сохранить».

- Whisper turbo — по умолчанию.
- GigaAM Сбера — меньше и лучше на русском.

Первый запуск сам скачивает модель, если её ещё нет.

## Где лежат данные

- Windows: `%APPDATA%\F1WhisperTyping`
- macOS: `~/Library/Application Support/F1WhisperTyping`
- Модели: кэш Hugging Face `~/.cache/huggingface/hub`

## Сборка и GitHub

`build.bat` → exe. При теге `v*` GitHub Actions собирает Windows-файл. Тексты для GitHub: README.md (RU+EN) и PROMO.md.

## Версия

`APP_VERSION` и `APP_UPDATED` в `settings.py`, шапка окна настроек.
