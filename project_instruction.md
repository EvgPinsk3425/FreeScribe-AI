# FreeScribe-AI — инструкция по проекту

Офлайн голосовой набор для Windows и macOS: горячая клавиша → речь → текст в активном окне.

## Запуск

- Windows: `start.bat` или `py -3.13 main.py`. Готовый exe: `release\FreeScribe-AI.exe` / Releases.
- macOS: `./start.command` или `python3 main.py`. Разрешить микрофон и Универсальный доступ.

Не запускать через случайный `python` из PATH (может быть другой интерпретатор без пакетов).

## Модели

Каталог `MODEL_CATALOG` в `settings.py`. В окне настроек: выбрать → «Скачать» → «Сохранить».

- Whisper turbo — по умолчанию.
- GigaAM Сбера — меньше и лучше на русском.

Первый запуск сам скачивает модель, если её ещё нет.

## Сигналы

В настройках: «Всплывающие подсказки у иконки» и «Звук при старте и окончании записи».

## Где лежат данные

- Windows: `%APPDATA%\FreeScribe-AI` (старые настройки из F1WhisperTyping подхватываются)
- macOS: `~/Library/Application Support/FreeScribe-AI`
- Модели: кэш Hugging Face `~/.cache/huggingface/hub`

## Сборка и GitHub

`build.bat` → `dist\FreeScribe-AI.exe`, копия в `release\`. При теге `v*` GitHub Actions собирает Windows-файл. Репозиторий: FreeScribe-AI. Тексты: README.md и PROMO.md.

## Версия

`APP_VERSION` и `APP_UPDATED` в `settings.py`, шапка окна настроек.
