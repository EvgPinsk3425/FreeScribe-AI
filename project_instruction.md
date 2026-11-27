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

В настройках: подсказки у иконки и список «Сигналы» (звук при старте / окончании / оба).
Кнопка «Обновить» рядом с версией — скачивает новый exe с GitHub Releases.
Птичка «Запускать при старте» — автозапуск с Windows.

## Где лежат данные

- Windows: `%APPDATA%\FreeScribe-AI` (старые настройки из F1WhisperTyping подхватываются)
- macOS: `~/Library/Application Support/FreeScribe-AI`
- Модели: кэш Hugging Face `~/.cache/huggingface/hub`

## Сборка и GitHub

`build.bat` → `dist\FreeScribe-AI.exe`, копия в `release\FreeScribe-AI.exe`. При теге `v*` GitHub Actions публикует exe в Releases. Репозиторий: **EvgPinsk3425/FreeScribe-AI**.

### Обязательно для агента (при любом изменении кода)

После правок Python/UI, влияющих на поведение приложения:

1. Поднять **APP_VERSION** и **APP_UPDATED** (`дд.мм.гггг чч:мм`) в `settings.py` (и в UI, если версия там видна).
2. **Собрать exe**: `py -3.13 -m PyInstaller --noconfirm WhisperTyping.spec` (или `build.bat` без `pause`).
3. Скопировать в `release\FreeScribe-AI.exe` (build.bat делает это сам).
4. **GitHub Releases**: закоммитить исходники, тег `vX.Y` (как **APP_VERSION**), `git push origin` и `git push origin vX.Y` — workflow прикрепит exe к релизу. Имя файла в релизе: **FreeScribe-AI.exe** (не F1WhisperTyping).
5. В ответе пользователю: версия, дата/время, что копировать на сервер/новый ПК — только свежий `release\FreeScribe-AI.exe`, не старые сборки.

Пользователям **не отдавать** старые exe с GitHub (например v2.3 / F1WhisperTyping) — только актуальный тег.

## Версия

На Windows Server иконка трея часто прячется за стрелкой ▲ у часов. При записи сверху экрана красная плашка «FreeScribe-AI · запись» (системный значок микрофона Windows — это не иконка программы).
