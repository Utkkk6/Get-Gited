<div align="center">

# Get Gited

**Одно рабочее пространство. Все ваши Git-репозитории.**

`SIMPLE. SAFE. SYNCED.`

[English](README.md) · [Русский](README.ru.md)

[![CI](https://github.com/Utkkk6/Get-Gited/actions/workflows/ci.yml/badge.svg)](https://github.com/Utkkk6/Get-Gited/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Windows-first](https://img.shields.io/badge/windows-first-0078D6?logo=windows&logoColor=white)](#установка)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#лицензия)

Десятки папок. Часть на GitHub. Часть только на диске. Где-то незапушенные коммиты, где-то отставание, грязное дерево или вообще не Git.

Я написал Get Gited как **таблицу всего рабочего пространства** — потом превью, потом безопасная запись. Это не обёртка, которая сама стреляет `git push`.

```text
scan → understand → preview → choose → execute → verify
```

никогда

```text
scan → YOLO git push
```

</div>

| Это | Это не |
| --- | --- |
| Один обзор локальных проектов + совпадений с GitHub | Полноценный Git-клиент |
| Сначала превью: push / ff-only pull / private publish / clone | Dropbox-синхронизация файлов |
| Клавиатурный пикер `[*]` (`gg`) и Textual TUI | Менеджер Issues / PR |
| `BLOCKED` с причиной, если запись опасна | Автокоммит, force push, merge или rebase |

```text
GET GITED                                          SIMPLE. SAFE. SYNCED.
One workspace. All your Git repos.
────────────────────────────────────────────────────────────────────────
mtime  ·  minimal  ·  guess off

  #  Sel  Project     GitHub            Status              Date        About
  1  [*]  ScreenNote  you/ScreenNote    REMOTE_AHEAD        2026-08-12  Capture the screen.
  2  [ ]  CLINQ       you/CLINQ         LOCAL_AHEAD         2026-08-11  Clinic queue app.
  3  [ ]  OldParser   you/OldParser     REMOTE_ONLY         —           —
  4  [ ]  NewTool     —                 LOCAL_ONLY          2026-08-10  Scratch CLI.

number  toggle   s1–s4  sort   u1–u5  ui   [Enter]  continue
q  back   e  exit   gg acpt --help  About consent
```

(Скриншотов в репозитории пока нет. Это реальная раскладка пикера.)

## Установка

Основная платформа — Windows. Пути вида `C:\Users\...` и `D:\Code` поддерживаются напрямую.

| Нужно | Проверка |
| --- | --- |
| **Python 3.12+** | `py -0p` — **на 3.11 пакет не встанет** |
| **Git** | `git --version` (должен быть в `PATH`) |
| **[GitHub CLI](https://cli.github.com/) `gh`** | `gh --version`, затем `gh auth login` |

Из клона, в **PowerShell**:

```powershell
cd "C:\Users\You\Desktop\Get Gited"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
gg --help
get-gited doctor
```

В приглашении должно быть `(.venv)`. Пока его нет, Windows не увидит `gg` / `get-gited`.

Без активации:

```powershell
.\.venv\Scripts\gg.exe --help
.\.venv\Scripts\get-gited.exe doctor
```

Если `Activate.ps1` блокируется:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Ловушка PATH (терминал редактора, venv, `gh`)

Это причина номер один, почему «поставил, а `gg` не находится».

- Встроенный терминал IDE часто держит тот `PATH`, с которым **эта** сессия стартовала. Установка в `.venv` старую вкладку не обновляет.
- `python` в этой вкладке может быть **системным**, а не из `.venv`. Тогда `pip install -e .` кладёт пакет не туда, и `gg` нет.
- `gh` / Git, поставленные через winget, часто появляются в `PATH` только после **полного перезапуска редактора** (или нового окна PowerShell).

Что делать, по порядку:

1. Закройте вкладку терминала. Откройте новую. Выполните `.\.venv\Scripts\Activate.ps1`. Должно появиться `(.venv)`.
2. `Get-Command python, gg, git, gh | Format-Table Name, Source`
3. `python -c "import sys; print(sys.executable)"` должен указывать внутрь `.venv`.
4. Всё ещё нет? Зовите exe напрямую: `.\.venv\Scripts\gg.exe doctor`
5. После установки Git или `gh` полностью закройте редактор и откройте снова, либо откройте свежий PowerShell снаружи.

`gg` — это алиас `get-gited` из `[project.scripts]`. Отдельный PATH руками править не нужно, если venv реально активен.

## Первые пять минут

```powershell
gg --help
gg doctor
gg status "C:\Users\You\Desktop"
gg "C:\Users\You\Desktop"          # пикер: цифры, превью, confirm
get-gited sync "C:\Users\You\Desktop" --dry-run
get-gited                          # Textual TUI
```

Пути с пробелами — в кавычках. Не вставляйте плейсхолдеры вроде `<твои папки>`: в PowerShell `<` — перенаправление.

Работают и `--help`, и `-h`. `get-gited` без подкоманды открывает TUI.

## Короткая команда (`gg`)

```powershell
gg                          # предложит текущую папку, затем сортировка + [*]
gg D:\Projects              # скан этого пути, затем сортировка + [*]
gg -y                       # скан cwd, пикер со всеми строками
gg --yes --sort mtime
gg status D:\Projects
gg doctor
gg acpt --help
gg ui                       # список из 5 видов
gg ui 2                     # выбрать по номеру
gg ui cards                 # выбрать по имени
```

**`gg -y` — это не «выполни всё».** Короткий `-y` только пропускает вопрос «эту папку?» и открывает пикер. Для записи всё равно нужны выбор и `[Enter]` на превью.

`get-gited sync --yes` — **это** «выполни всё»: весь план без пикера. Другая команда, другой смысл флага.

## Клавиатура

| Ввод | Что делает |
| --- | --- |
| `1`, `2`, … | Переключить строку `[*]` / `[ ]` |
| `[Enter]` на таблице | Превью запланированных операций |
| `[Enter]` на превью | **Выполнить** |
| `q` | На экран назад (пикер → сортировка → пикер). **Не** выход |
| `e` | Выход. На превью тоже `e` |
| `s1`–`s4` | Сортировка, не выходя из таблицы (`mtime`, `sync`, `presence`, `size`) |
| `u1`–`u5` | Тема терминала (`frame`, `minimal`, `hud`, `cards`, `poster`) |
| `i` | Догадки для колонки About (по умолчанию выкл.) |

Пять видов: **frame** (классические рамки), **minimal** (по умолчанию, широкая таблица), **hud** (двойная линия), **cards** (две строки на проект), **poster** (заголовок сверху). Остаток ширины терминала уходит в **About**, чтобы шапка не обрезалась до `Ab...`.

About — выжимка из README или `—`. Другие файлы проекта не читаются, пока вы не дадите согласие:

```powershell
gg acpt --on     # разрешить описания из pyproject.toml / package.json / Cargo.toml
gg acpt --off    # снова только README или —
gg acpt --help
```

## Команды

| Команда | Что делает |
| --- | --- |
| `get-gited` | TUI рабочего пространства |
| `get-gited doctor` | Python / Git / `gh` / auth / конфиг — **проекты не сканирует** |
| `get-gited scan D:\Projects` | Найти локальные проекты |
| `get-gited status D:\Projects` | Таблица local + GitHub |
| `get-gited status D:\Projects --sort mtime` | Та же таблица, с сортировкой |
| `get-gited sync D:\Projects` | В TTY: сортировка + пикер `[*]`, превью, confirm |
| `get-gited sync D:\Projects --dry-run` | Превью — **без записи** |
| `get-gited sync D:\Projects --yes` | Выполнить **весь** план (без пикера) |
| `gg` / `gg PATH` / `gg -y` | Короткая команда — см. выше |
| `gg ui` / `gg ui 2` | Вид терминала (5 тем) |
| `gg acpt` | Согласие для колонки About |

Можно передать один или несколько корней. Если не указать — берутся `[[roots]]` из конфига.

`git fetch` **не** входит в dry-run. Свежесть remote — отдельный Refresh.

## Как читать таблицу статуса

| Статус | Смысл |
| --- | --- |
| `SYNCED` | Локальная ветка совпадает с upstream |
| `SYNCED (UNCOMMITTED)` | Синхронно, но в дереве есть незакоммиченные изменения |
| `LOCAL_AHEAD` | Есть незапушенные коммиты |
| `REMOTE_AHEAD` | Можно fast-forward pull (если дерево чистое) |
| `DIVERGED` | И локально, и на remote есть уникальные коммиты — **блок**, без авто-merge/rebase |
| `NO_REMOTE` | Git-репозиторий, remote не настроен |
| `LOCAL_ONLY` | Локальный проект, точного совпадения на GitHub нет |
| `REMOTE_ONLY` | Есть на GitHub, локально не склонирован |
| `NO_GIT` | Похоже на проект, но это не Git-репозиторий |
| `BLOCKED` | Запись была бы небезопасна (секреты, коллизия клона, detached HEAD, …) |
| `ERROR` | Не удалось проинспектировать эту строку |
| `DUP` | Возможный дубликат (тот же remote, имя или корневой коммит) |

`UNCOMMITTED` — бейдж поверх основного статуса.

## Типичный цикл «сел за ноут»

```text
ScreenNote   REMOTE AHEAD   → pull (только ff-only)
CLINQ        LOCAL AHEAD    → push уже существующих коммитов
OldParser    REMOTE ONLY    → clone в выбранный корень
NewTool      LOCAL ONLY     → publish (по умолчанию private)
```

Сначала всегда превью:

```powershell
get-gited sync D:\Projects --dry-run
```

Если план верный **и** нужна вся очередь без пикера:

```powershell
get-gited sync D:\Projects --yes
```

Без `--yes` неинтерактивный `sync` печатает план и останавливается. Интерактивный `gg` всё равно ждёт `[Enter]` на превью.

## Безопасность

Get Gited **никогда** сам не сделает:

- force-push
- `git reset --hard` / `git clean -fd`
- переписывание истории
- merge разошедшихся веток или rebase
- автокоммит изменений в рабочем дереве
- перезапись существующей папки при clone
- слепую замену Git remote
- публикацию репозитория как public, пока вы это не выберете
- печать найденного секрета целиком

Если безопасного действия нет — статус `BLOCKED` (или `ERROR`), а не «умное» автоматическое лечение.

Dry-run не меняет рабочие деревья, Git refs (включая remote-tracking), GitHub и конфиг.

Перед первой публикацией идёт детерминированный preflight на секреты и слишком большие файлы.

## Конфигурация

Необязательна. Путь по умолчанию в Windows:

```text
%APPDATA%\get-gited\config.toml
```

Обычно `C:\Users\<вы>\AppData\Roaming\get-gited\config.toml`.

```toml
[[roots]]
path = "D:\\Projects"
profile = "personal"
default_visibility = "private"

[scan]
max_depth = 6

[ignore]
paths = ["D:\\Projects\\archive"]

[privacy]
infer_about = false

[ui]
theme = "minimal"
```

Токены в этот файл не класть. Авторизация — через `gh`. Get Gited GitHub-токены не хранит.

## Разработка

```powershell
python -m pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
mypy
python -m build
```

## Лицензия

MIT. Текст — в [`LICENSE`](LICENSE).

Этот файл **и есть** лицензия. На GitHub ничего отдельно «подавать» не нужно: кладёте `LICENSE` в репозиторий, GitHub показывает то, что лежит в дереве.
