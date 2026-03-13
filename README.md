# FinAccountingApp

Графическое приложение для персонального финансового учёта с мультивалютностью, категориями и отчётами.

## 📋 Оглавление

- [Быстрый старт](#-быстрый-старт)
- [Использование приложения](#️-использование-приложения)
- [Архитектура проекта](#️-архитектура-проекта)
- [Программный API](#-программный-api)
- [Файловая структура](#-файловая-структура)
- [Тесты](#-тесты)
- [Поддерживаемые валюты](#-поддерживаемые-валюты)

---

## 🚀 Быстрый старт

### Системные требования

- Python 3.10+
- pip

### Установка

```bash
# Перейдите в директорию проекта
cd "Проект ФУ/project"

# Создайте виртуальное окружение
python -m venv .venv

# Активация (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Активация (Windows CMD)
.venv\Scripts\activate.bat

# Активация (Linux/macOS)
source .venv/bin/activate

# Установка runtime-зависимостей
pip install -r requirements.txt

# Установка dev-зависимостей (тесты, coverage)
pip install -r requirements-dev.txt
```

### Первый запуск

```bash
python main.py
```

После запуска откроется графическое окно приложения Financial Accounting.

---

## 🖥️ Использование приложения

### Главное окно

После запуска `python main.py` из каталога `project` откроется окно с вкладками управления и блоком инфографики.

Вкладки и действия:

- `Infographics` — отображение инфографики (круговая диаграмма, гистограммы) с возможностью фильтрации по месяцу/году.
- `Operations` — управление записями и переводами (добавление, удаление, импорт/экспорт).
- `Reports` — генерация отчётов, экспорт.
- `Settings` — управление обязательными расходами и кошельками.

Инфографика:

- Круговая диаграмма расходов по категориям с фильтром месяца.
- Гистограмма доходов/расходов по дням месяца.
- Гистограмма доходов/расходов по месяцам года.

Доходы отображаются зелёным, расходы — красным. Для круговой диаграммы малые категории агрегируются в «Other». Список категорий в легенде прокручивается. Исключены записи с категорией "Transfer" для повышения точности анализа и консистентности.

### Добавление дохода/расхода

1. Откройте вкладку `Operations`.
2. В блоке `Add operation` выберите тип операции (`Income` или `Expense`).
3. Укажите дату в формате `YYYY-MM-DD` (дата не может быть в будущем).
4. Введите сумму.
5. Укажите валюту (по умолчанию `KZT`).
6. Укажите категорию (по умолчанию `General`).
7. При необходимости заполните `Description`.
8. Нажмите `Save`.

Сумма конвертируется в базовую валюту `KZT` по текущим курсам сервиса валют. После добавления записи список автоматически обновляется.

### Добавление перевода

1. Откройте вкладку `Operations`.
2. В блоке `Transfer` выберите `From wallet` и `To wallet`.
3. Укажите дату в формате `YYYY-MM-DD` (дата не может быть в будущем).
4. Введите сумму.
5. Укажите валюту (по умолчанию `KZT`).
6. При необходимости укажите `Commission` и валюту комиссии.
7. При необходимости заполните `Description`.
8. Нажмите `Save`.

### Удаление записи

1. Откройте вкладку `Operations`.
2. Выберите запись из списка.
3. Нажмите `Delete Selected`. Появится сообщение об удалении с индексом записи или ID перевода.

### Удаление всех записей

1. Откройте вкладку `Operations`.
2. В блоке `List of operations` выберите запись из списка.
3. Нажмите `Delete All Records` и подтвердите удаление. Записи будут удалены без возможности восстановления, а список записей обновится.

### Inline-редактирование записи

1. Откройте вкладку `Operations`.
2. Выберите запись в списке.
3. Нажмите `Edit`.
4. Измените `Date`, `Wallet`, `Amount KZT`, `Category` и при необходимости `Description`.
5. Нажмите `Save`.

Изменение выполняется через immutable-модель: создаётся новая версия записи, `rate_at_operation` пересчитывается автоматически, а `description` остаётся необязательным. Дата валидируется (формат `YYYY-MM-DD`, не в будущем), кошелёк должен быть активным. Для transfer-связанных записей и записей с категорией `"Transfer"` редактирование запрещено.

### Генерация отчёта

1. Откройте вкладку `Reports`.
2. Введите фильтры (опционально):
    - `Period` — начало периода (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`).
    - `Period end` — конец периода (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`).
    - `Category` — фильтр по категории.
3. Выберите один кошелёк для генерации отчёта по нему или все кошельки.
4. Включите опции:
    - `Group by category` — группировка по категориям.
    - `Display as table` — табличный формат.
5. Нажмите `Generate`.

Внизу отображается дополнительная таблица «Monthly Income/Expense Summary» для выбранного года и месяцев.

Экспорт отчёта:

- Форматы: `CSV`, `XLSX`, `PDF`.
- В заголовке отчёта указывается диапазон периода:
  `Transaction statement (<start_date> - <end_date>)`.
- Если `Period end` не указан, в качестве конца периода используется текущая дата.
- Кроме основных записей, в `XLSX` добавляется лист `Yearly Report` с помесячной сводкой. Также создаётся второй, промежуточный лист `By Category` с группировкой записей по категориям и подсуммами.
- В `PDF` помесячная сводка остаётся, а после основной выписки добавляются таблицы с разбивкой по категориям (каждая категория — отдельная таблица с подсуммой).

### Начальный баланс в фильтрованных отчётах

- `Initial balance` — начальный остаток всей истории; не зависит от фильтра.
- `Opening balance` — остаток на начало выбранного периода; вычисляется динамически.
- Для фильтра `YYYY` старт периода: `YYYY-01-01`.
- Для фильтра `YYYY-MM` старт периода: `YYYY-MM-01`.
- Для фильтра `YYYY-MM-DD` старт периода: указанная дата.
- Фильтр периода не может указывать на будущую дату (для всех форматов).

### Управление обязательными расходами

Во вкладке `Settings`, в блоке `Mandatory Expenses` доступны операции:

- `Add` — добавить обязательный расход.
- `Edit` — отредактировать выбранный шаблон (inline).
- `Delete` — удалить выбранный.
- `Delete All` — удалить все.
- `Add to Records` — добавить выбранный расход в записи с указанной датой.
- Селектор формата файла для импорта/экспорта.
- `Import` — импорт обязательных расходов.
- `Export` — экспорт обязательных расходов.

Поля обязательного расхода:

- `Wallet`, `Amount`, `Currency`, `Category` (по умолчанию `Mandatory`), `Description` (обязательно), `Period` (`daily`, `weekly`, `monthly`, `yearly`).

#### Поля шаблона обязательного расхода

- `Date` (необязательно, `YYYY-MM-DD`) — если указана, флаг `auto_pay` устанавливается автоматически
- `auto_pay` — вычисляется из `date`: заполнена → `True`, пусто → `False`

Поведение `auto_pay`:

- Применяется ко всем шаблонам с непустым `date` (т.е. `auto_pay=True`).
- Автоплатёж запускается не раньше `date` шаблона (anchor date).
- Частота определяется `period`:
  `daily` — 1 запись в день;
  `weekly` — 1 запись в неделю в день недели как в `date`;
  `monthly` — 1 запись в месяц с тем же `DD` (если день больше последнего дня месяца, используется последний день месяца);
  `yearly` — 1 запись в год с тем же `MM-DD` (дата корректируется для несуществующих дней, например 29 февраля).

#### Inline-редактирование шаблона

1. Выберите шаблон в списке.
2. Нажмите `Edit`.
3. Измените `Amount KZT`, `Date`, `Period` и/или `Wallet`.
4. Нажмите `Save`.

`amount_kzt` валидируется как число, `date` — форматом `YYYY-MM-DD`.
`auto_pay` пересчитывается автоматически при изменении даты.

Импорт/экспорт обязательных расходов:

- Импорт: `CSV`, `XLSX`.
- Экспорт: `CSV`, `XLSX`.
- Runtime-шаблоны в SQLite теперь могут хранить `date` и производный флаг `auto_pay`.
- Для `mandatory_expenses` поле `date` теперь сохраняется и восстанавливается в `CSV`/`XLSX`.

### Finance Audit

Во вкладке `Settings`, в блоке `Finance Audit` доступна кнопка `Run Audit`.

По нажатию выполняется диагностика базы данных в режиме только чтения.
Аудит проверяет:

- системный кошелёк (`id=1` существует и имеет `system=1`)
- целостность пар transfer-записей (ровно 2 связанных записи: income + expense)
- согласованность агрегата `transfers` с привязанными `expense`/`income` записями
- инварианты transfer-связанных записей (консистентность wallet_id, сумм, валют и категорий)
- корректность расчёта amount_kzt (amount_original × rate_at_operation)
- положительность amount_original и amount_kzt в records / transfers / mandatory_expenses
- положительность rate_at_operation для всех записей
- валидность поля date (формат YYYY-MM-DD, не в будущем)
- наличие кода валюты (currency не пустой)
- консистентность `mandatory_expenses.date` и `auto_pay` (`auto_pay` соответствует наличию `date`)

Результат отображается в модальном диалоге с разбивкой на три секции:
`Errors`, `Warnings`, `Passed`. База данных не изменяется.

### Balance Engine

`BalanceService` — аналитический сервис, вычисляющий финансовое состояние системы из истории операций.
Баланс никогда не хранится в базе — он всегда вычисляется динамически.

Доступные методы:

- `get_wallet_balance(wallet_id, date=None)` — баланс кошелька (опционально на дату)
- `get_wallet_balances(date=None)` — балансы всех активных кошельков
- `get_total_balance(date=None)` — общий баланс системы (net worth)
- `get_cashflow(start_date, end_date)` — доходы, расходы и cashflow за период
- `get_income(start_date, end_date)` — доходы за период
- `get_expenses(start_date, end_date)` — расходы за период

Сервис строго только читает данные — база никогда не изменяется.
Переводы (`category='Transfer'`) исключаются из cashflow-расчётов во избежание двойного счёта.

### Timeline Engine

Аналитический сервис для построения исторической динамики финансов.

| Метод | Описание |
| --- | --- |
| `get_net_worth_timeline()` | Net worth (KZT) на конец каждого месяца |
| `get_monthly_cashflow(start_date, end_date)` | Доходы, расходы, сальдо по месяцам |
| `get_cumulative_income_expense()` | Накопительные суммы доходов и расходов |

Все методы read-only. Переводы (`transfer_id IS NOT NULL`) исключаются из cashflow-расчётов,
чтобы избежать двойного счёта; в net worth включаются (expense + income = 0, нейтральны).
Стартовый баланс (`wallets.initial_balance`) учитывается в каждой точке timeline.

### Импорт финансовых записей

Импорт выполняется через `Import` во вкладке `Operations`.

Архитектура импорта:

- `ImportService -> FinancialController (FinanceService) -> RecordRepository/Storage`.
- Импорт не создаёт записи напрямую через `JsonStorage/SQLiteStorage`.
- Переводы создаются только через `create_transfer(...)` сервиса (инвариант `1 transfer = 2 record` сохраняется).
- Перед записью приложение выполняет dry-run: полный parse и validation без записи в SQLite.
- Во вкладке `Operations` после dry-run показывается модальный preview-диалог; пользователь подтверждает или отменяет реальный импорт.
- Реальный импорт выполняется в сервисной транзакции и возвращает структурированный `ImportResult`.
- Для `Full Backup` сохраняются исходные `amount_kzt` и `rate_at_operation` из файла.
- Для `Current Rate` применяется пересчёт через `CurrencyService.get_rate(...)`.
- В parser-слое действуют лимиты безопасности (размер файла, число строк, размер CSV-поля).
- Ошибочные строки не записываются в базу и попадают в `ImportResult.errors`; валидные строки могут быть импортированы.
- Если dry-run не нашёл ни одной валидной строки (`imported == 0`), диалог preview не позволяет продолжить импорт.
- `initial_balance` в импортируемом файле допускается только один раз. Повторные строки считаются ошибкой и попадают в preview/result.
- `wallet_id` в импортируемых данных должен быть целым положительным числом (без дробной части).
- Нечисловые и нефинитные значения (`NaN`, `inf`) в числовых полях импорта отклоняются.

Форматы:

- `JSON`, `CSV`, `XLSX`.
- Pipeline импорта: `parser -> dry-run validation -> user confirmation -> SQLite transaction`.
- Для `CSV/XLSX` реальный импорт заменяет runtime-данные валидными строками из файла; ошибочные строки остаются только в отчёте импорта.
- Для readonly `JSON` snapshot требуется `force=True`; проверка readonly/checksum выполняется ещё до этапа commit.

Формат данных:

- **CSV/XLSX данных (import/export):**  
  `date,type,wallet_id,category,amount_original,currency,rate_at_operation,amount_kzt,description,period,transfer_id,from_wallet_id,to_wallet_id`.
- `wallet_id` — идентификатор кошелька, в котором была совершена операция.
- `transfer_id` — идентификатор перевода между кошельками.
- `from_wallet_id` — идентификатор исходного кошелька при переводе.
- `to_wallet_id` — идентификатор целевого кошелька при переводе.
- Поддерживается legacy-импорт (старые файлы с полем `amount` или с колонкой `Amount (KZT)`).
- Все существующие записи заменяются данными из файла.

Важно:

- `CSV/XLSX отчёта` и `CSV/XLSX данных` — это разные форматы.
- `CSV/XLSX отчёта` используется только для чтения пользователем и **не должен** использоваться как источник данных для импорта.

### ImportPolicy

Для импорта записей доступны 3 режима:

- `Full Backup` (`ImportPolicy.FULL_BACKUP`)  
  Используется для полного импорта с фиксированным курсом операции. Ожидаемый формат строк:
  `date,type,wallet_id,category,amount_original,currency,rate_at_operation,amount_kzt,description,period,transfer_id,from_wallet_id,to_wallet_id`.
- `Current Rate` (`ImportPolicy.CURRENT_RATE`)
  Для каждой импортируемой строки курс берётся на момент импорта через `CurrencyService.get_rate(currency)`, а `rate_at_operation` и `amount_kzt` пересчитываются и фиксируются заново.
- `Legacy Import` (`ImportPolicy.LEGACY`)  
  Старый формат `date,type,category,amount` автоматически мигрируется в новый:
  `currency="KZT"`, `rate_at_operation=1.0`, `amount_kzt=amount`.

Все режимы выполняют построчную валидацию и формируют `ImportResult`
(`imported`, `skipped`, `errors`, `dry_run`).

### Dry-run Mode

- Перед записью в базу данных приложение выполняет полный dry-run: файл анализируется и проверяется без изменения каких-либо записей.
- Диалоговое окно предварительного просмотра показывает количество записей для импорта, пропущенные строки и любые ошибки.
- Пользователь явно подтверждает или отменяет изменение данных.

### Backup

Полный backup реализован в формате `JSON` в двух вариантах:

- `Snapshot backup` (по умолчанию):
  - корень: `meta` + `data`;
  - `meta.readonly=true`, `meta.checksum` (SHA256 от `data`);
  - checksum считается детерминированно по `json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
- `Technical backup` (`readonly=False`):
  - legacy-совместимый JSON без `meta` и без checksum;
  - используется для обычного pipeline без readonly-ограничения.
- Метаданные snapshot:
  - `meta.app_version` берётся из `version.py`;
  - `meta.storage` задаётся вызывающим кодом и не хардкодится в `sqlite`.
- Вкладка `Settings` содержит кнопки:
  - `Export Full Backup`
  - `Import Full Backup`
- Импорт `readonly` snapshot требует `force=True` (или подтверждение force в UI).

Backup восстанавливает:

- кошельки с полями `id/name/currency/balance`;
- все записи с полями `type/date/wallet_id/transfer_id/category/amount_original/currency/rate_at_operation/amount_kzt/category/description`;
- все обязательные расходы с `date/description/period`;
- все переводы между кошельками.

### FX Revaluation

`Report` поддерживает:

- `net_worth_fixed()` — чистая стоимость активов на момент записи;
- `net_worth_current()` — чистая стоимость активов по текущему курсу;
- `total_fixed()` — бухгалтерский итог по курсу на дату операции;
- `total_current(currency_service)` — итог по текущему курсу;
- `fx_difference(currency_service)` — переоценка (`current - fixed`);
- `total()` — alias для `total_fixed()` (backward compatibility).

### Migration

Правила миграции старых форматов:

- legacy `amount` -> `amount_original`;
- отсутствующая валюта -> `KZT`;
- отсутствующий курс -> `1.0`;
- отсутствующий `amount_kzt` -> вычисляется по политике импорта;
- недопустимые строки пропускаются и попадают в список ошибок.

### Хранение данных

Runtime-хранилище приложения — только SQLite (`finance.db`).
JSON (`data.json`) больше не используется как backend для работы приложения и нужен только для:

- импорта JSON;
- экспорта JSON;
- резервных копий.

При startup-потоке после проверки целостности SQLite выполняется экспорт текущего состояния в `data.json`.
Этот экспорт теперь сохраняет `mandatory_expenses.date`, поэтому JSON-слепок не теряет дату шаблона.

Для работы со storage используется отдельный слой `storage/`:

- `storage/base.py` — контракт `Storage` (только data-access операции).
- `storage/json_storage.py` — JSON-адаптер только для import/export/backup сценариев.
- `storage/sqlite_storage.py` — `SQLiteStorage` на стандартном `sqlite3`.
- `db/schema.sql` — SQL-схема таблиц `wallets`, `records`, `transfers`, `mandatory_expenses`.

### Миграция JSON -> SQLite

Для безопасного переноса данных используется скрипт `migrate_json_to_sqlite.py`.

Примеры запуска:

```bash
# Проверка без записи в SQLite
python migrate_json_to_sqlite.py --dry-run

# Полная миграция
python migrate_json_to_sqlite.py --json-path data.json --sqlite-path finance.db
```

Что делает скрипт:

- загружает данные через `JsonStorage`;
- пишет в SQLite в одной явной транзакции в порядке:
  `wallets -> transfers -> records -> mandatory_expenses`;
- сохраняет существующие `id` (или строит mapping `old_id -> new_id` при авто-генерации);
- валидирует целостность и сверяет балансы/`net worth`;
- делает `rollback` при любой ошибке или расхождении.
- безопасен к повторному запуску: если SQLite уже содержит эквивалентный набор данных, миграция пропускается без ошибки.

### Конфигурация runtime storage

В модуле `config.py` задаются пути:

- `SQLITE_PATH = "finance.db"`
- `JSON_PATH = "data.json"`
- `JSON_BACKUP_KEEP_LAST = 30` — сколько timestamped JSON-бэкапов хранить в `project/backups/` (старые удаляются при старте после создания нового).

Пути резолвятся относительно каталога `project`, поэтому `finance.db` и `data.json` создаются внутри `project` даже при запуске из другой папки.

Инициализация происходит через `bootstrap.py`:

- приложение всегда использует SQLite как runtime storage;
- если `finance.db` отсутствует, база создаётся автоматически и schema инициализируется при старте;
- при старте обеспечивается наличие системного кошелька;
- выполняется проверка внутренней целостности SQLite:
  `PRAGMA foreign_key_check`, корректность связок transfer (`ровно 2 записи: income+expense`),
  отсутствие orphan records и CHECK-like нарушений;
- после успешной проверки SQLite автоматически экспортируется в `data.json`;
- JSON bootstrap и работа приложения напрямую с `data.json` удалены.

Поведение SQLite по идентификаторам:

- Для рабочих операций `INSERT` выполняется без ручной передачи `id`; `id` генерируется SQLite.
- Для сценариев полной замены данных (`replace_all_data`, импорт backup, нормализация после импорта) выполняется переиндексация сущностей в диапазон `1..N`.
- При такой переиндексации ссылки (`wallet_id`, `transfer_id`, `from_wallet_id`, `to_wallet_id`) ремапятся атомарно, чтобы сохранить целостность связей.
- После очистки таблиц сбрасывается `sqlite_sequence`, чтобы новые записи снова начинались с `1`.
- Проверка равенства данных до/после импорта должна выполняться по бизнес-полям и инвариантам, а не по конкретным значениям `id`.

---

## 🏗️ Архитектура проекта

Проект следует слоистой архитектуре:

- `domain/` — бизнес‑модели и правила (записи, отчёты, аудит данных, валидация дат и периодов, валюты, кошельки, transfers).
- `app/` — сценарии использования (use cases), включая запуск аудита, и адаптер сервиса валют.
- `infrastructure/` — JSON и SQLite реализации `RecordRepository`.
- `storage/` — абстракция хранилища и адаптеры JSON/SQLite.
- `db/` — SQL-схема для SQLite.
- `bootstrap.py` — инициализация SQLite и стартовая валидация.
- `backup.py` — backup JSON и экспорт SQLite -> JSON.
- `config.py` — пути runtime SQLite и JSON import/export.
- `services/` — сервисный слой для импорта, read-only аудита и балансовой аналитики SQLite.
- `utils/` — импорт/экспорт и подготовка данных для графиков.
- `gui/` — GUI слой (Tkinter).

Поток данных для GUI:

- UI (Tkinter) → `gui/controllers.py` → `app/use_cases.py` → `infrastructure/sqlite_repository.py` → `finance.db`.

Связь домена:

- `Record` принадлежит `Wallet` через `record.wallet_id`.
- `Transfer` связывает две записи (`expense`/`income`) через `transfer_id`.
- Комиссия transfer хранится отдельной записью `Expense` (категория `Commission`) и не входит в пару связанных transfer-записей.

### Immutable Domain Model

- `Record` неизменяемый (`@dataclass(frozen=True)`), включая идентификатор `id`.
- Любое изменение финансовой записи создаёт новый объект, а не мутирует старый.
- Для обновления суммы используется `with_updated_amount_kzt(new_amount_kzt)`.
- Такой подход защищает целостность финансовых данных и упрощает переход на SQLite.

---

## 📝 Программный API

Ниже — ключевые классы и функции, синхронизированные с актуальным кодом.

### Domain

`domain/currency.py`

- `CurrencyService` — конвертация валют в базовую (`KZT`).

`domain/audit.py`

- `AuditSeverity` — enum уровня результата проверки (`ok`, `warning`, `error`).
- `AuditFinding(check, severity, message, detail="")` — отдельное наблюдение аудита.
- `AuditReport(findings, db_path)` — итог аудита с группировкой по `errors`, `warnings`, `passed`.
- `summary()` — краткая сводка результата аудита.

`domain/errors.py`

- `DomainError` — ошибка домена (выбрасывается при нарушении доменных инвариантов).

`domain/import_policy.py`

- `ImportPolicy` — import policy (enum).

`domain/import_result.py`

- `ImportResult(imported, skipped, errors, dry_run=False)` — неизменяемый результат dry-run или реального импорта (`errors` хранится как `tuple[str, ...]`).
- `summary()` — краткая строка результата; для dry-run добавляет префикс `[DRY-RUN]`.

`domain/records.py`

- `Record` — базовая запись (абстрактный класс). Cодержит обязательный `wallet_id` и опциональный `transfer_id`.
- `Record.id` — обязательный идентификатор записи.
- `Record.with_updated_amount_kzt(new_amount_kzt)` — возвращает новый экземпляр записи с пересчитанным `rate_at_operation`.
- `IncomeRecord` — доход.
- `ExpenseRecord` — расход.
- `MandatoryExpenseRecord` — обязательный расход с `description` и `period`.

`domain/reports.py`

- `Report(records, initial_balance=0.0)` — отчёт.
- `total_fixed()` — итог по курсу операции (бухгалтерский режим).
- `total_current(currency_service)` — итог по текущему курсу.
- `fx_difference(currency_service)` — курсовая разница.
- `total()` — алиас `total_fixed()` для обратной совместимости.
- `opening_balance(start_date)` — вычисляет баланс на начало периода: `initial_balance + все записи с date < start_date`.
- `filter_by_period(prefix)` — фильтрация по префиксу даты.
- `filter_by_period_range(start_prefix, end_prefix)` — фильтрация по диапазону дат.
- `filter_by_category(category)` — фильтрация по категории.
- `grouped_by_category()` — группировка по категориям с сохранением контекста отчёта (`balance_label`, диапазон периода).
- `sorted_by_date()` — сортировка по дате.
- `net_profit_fixed()` — чистая прибыль по фиксированным курсам.
- `monthly_income_expense_rows(year=None, up_to_month=None)` — агрегаты по месяцам.
- `monthly_income_expense_table(year=None, up_to_month=None)` — таблица по месяцам.
- `as_table(summary_mode="full"|"total_only")` — табличный вывод.
- `to_csv(filepath)` и `from_csv(filepath)` — экспорт отчёта и backward-compatible импорт.

`domain/wallets.py`

- `Wallet` — кошелёк (`allow_negative`, `is_active`).

`domain/transfers.py`

- `Transfer` — агрегат перевода между кошельками.

`domain/validation.py`

- `parse_ymd(value)` — парсинг и валидация даты `YYYY-MM-DD`.
- `ensure_not_future(date)` — запрет будущих дат.
- `ensure_valid_period(period)` — валидация периодов.
- `parse_report_period_start(value)` — валидация фильтра отчёта (`YYYY`/`YYYY-MM`/`YYYY-MM-DD`) и вычисление даты старта периода без будущих дат.
- `parse_report_period_end(value)` — валидация конца периода отчёта (`YYYY`/`YYYY-MM`/`YYYY-MM-DD`) и вычисление даты конца периода без будущих дат.

### Application

`app/services.py`

- `CurrencyService(rates=None, base="KZT", use_online=False)` — адаптер для доменного сервиса.
- При `use_online=True` пытается загрузить курсы НБ РК и кэширует в `currency_rates.json`.

`app/use_cases.py`

- `CreateIncome.execute(date, wallet_id, amount, currency, category="General", description="", amount_kzt=None, rate_at_operation=None)`.
- `CreateExpense.execute(date, wallet_id, amount, currency, category="General", description="", amount_kzt=None, rate_at_operation=None)`.
- `GenerateReport.execute(wallet_id=None)` → `Report` с учётом начального остатка.
- `CreateWallet.execute(name, currency, initial_balance, allow_negative=False)` — создание нового кошелька.
- `GetWallets.execute()` — все кошельки.
- `GetActiveWallets.execute()` — активные кошельки.
- `SoftDeleteWallet.execute(wallet_id)` — безопасный soft delete.
- `CalculateWalletBalance.execute(wallet_id)` — вычисление баланса кошелька.
- `CalculateNetWorth.execute_fixed()` — вычисление чистых активов по фиксированным курсам.
- `CalculateNetWorth.execute_current()` — вычисление чистых активов по текущим курсам.
- `CreateTransfer.execute(from_wallet_id, to_wallet_id, transfer_date, amount_original, currency, description="", commission_amount=0.0, commission_currency=None, amount_kzt=None, rate_at_operation=None)` — создание перевода между кошельками.
- `DeleteTransfer.execute(transfer_id)` — каскадное удаление transfer-агрегата.
- `DeleteRecord.execute(index)`.
- `DeleteAllRecords.execute()`.
- `ImportFromCSV.execute(filepath)` — импорт и полная замена записей (CSV, `ImportPolicy.FULL_BACKUP`).
- `CreateMandatoryExpense.execute(wallet_id=1, amount, currency, category, description, period, date="", amount_kzt=None, rate_at_operation=None)`.
- `ApplyMandatoryAutoPayments.execute(today=None)` — создаёт due-записи обязательных расходов для шаблонов с `auto_pay=True` по всем периодам (`daily/weekly/monthly/yearly`).
- `GetMandatoryExpenses.execute()`.
- `DeleteMandatoryExpense.execute(index)`.
- `DeleteAllMandatoryExpenses.execute()`.
- `AddMandatoryExpenseToReport.execute(index, date)`.
- `RunAudit.execute()` — запускает read-only аудит данных и возвращает `AuditReport`.

`app/record_service.py`

- `RecordService.update_amount_kzt(record_id, new_amount_kzt)` — безопасное обновление суммы через immutable-модель и repository replace.
- `RecordService.update_record_inline(record_id, *, new_amount_kzt, new_category, new_description="", new_date=None, new_wallet_id=None)` — inline-редактирование `Amount KZT` + `Category` (+ `Description`) + (`Date`/`Wallet`).
- `RecordService.update_mandatory_amount_kzt(expense_id, new_amount_kzt)` — обновляет `amount_kzt` и пересчитывает `rate_at_operation`.
- `RecordService.update_mandatory_date(expense_id, new_date)` — обновляет `date` и вычисляет `auto_pay`.
- `RecordService.update_mandatory_wallet_id(expense_id, new_wallet_id)` — меняет кошелёк шаблона.
- `RecordService.update_mandatory_period(expense_id, new_period)` — меняет период шаблона.

### Infrastructure

`infrastructure/repositories.py`

- `RecordRepository` — интерфейс репозитория.
- `JsonFileRecordRepository(file_path="data.json")` — JSON‑репозиторий для backup/import/export сценариев.

`infrastructure/sqlite_repository.py`

- `SQLiteRecordRepository(db_path="finance.db")` — SQLite-реализация `RecordRepository` для сервисного слоя.
- `db_path` — путь к текущей SQLite-базе для отчёта аудита.
- `query_all(...)` / `query_one(...)` — публичные read-only query API для bootstrap и audit-сценариев.

`storage/base.py`

- `Storage` — минимальный контракт хранения (`get/save` для wallets/records/transfers и `get` для mandatory expenses).

`storage/json_storage.py`

- `JsonStorage(file_path="data.json")` — JSON-обёртка только для import/export/backup сценариев.

`storage/sqlite_storage.py`

- `SQLiteStorage(db_path="records.db")` — SQLite-адаптер на `sqlite3`, включает:
  - `PRAGMA foreign_keys = ON`;
  - `PRAGMA journal_mode = WAL`;
  - чтение/запись доменных объектов без дублирования бизнес-логики.

`db/schema.sql`

- SQL-схема БД: таблицы `wallets`, `records`, `transfers`, `mandatory_expenses`, ограничения и индексы.

### GUI

`gui/tkinter_gui.py`

- `FinancialApp` — основной класс приложения с Tkinter.

`gui/tabs/infographics_tab.py`

- `InfographicsTabBindings` — класс для привязки событий к элементам интерфейса вкладки `Infographics`.
- `build_infographics_tab(parent, on_chart_filter_change, on_refresh_charts, on_legend_mousewheel, bind_all, after, after_cancel)` — метод для построения интерфейса вкладки `Infographics`. Эта вкладка отображает диаграммы и сводки по финансовым данным.

`gui/tabs/operations_tab.py`

- `OperationsTabContext` — контекст вкладки операций.
- `OperationsTabBindings` — класс для привязки событий к элементам интерфейса вкладки `Operations`.
- `show_import_preview_dialog(parent, filepath, policy_label, preview, force=False)` — модальный preview-диалог dry-run импорта.
- `build_operations_tab(parent, context, import_formats)` — метод для построения интерфейса вкладки `Operations`. Эта вкладка поддерживает добавление и удаление записей, редактирование валютных значений, создание переводов и двухшаговый import flow `dry-run -> preview -> commit`.

`gui/tabs/reports_tab.py`

- `ReportTabContext` — контекст вкладки отчетов.
- `build_reports_tab(parent, context)` — метод для построения интерфейса вкладки `Reports`. Эта вкладка поддерживает 2 режима итогов:
  - `По курсу операции`
  - `По текущему курсу`
- Курсовая разница выводится отдельной строкой (`FX Difference`).
- Месячные агрегаты и графики всегда считаются в фиксированном режиме (`amount_kzt`).

`gui/tabs/settings_tab.py`

- `SettingsTabContext` — контекст вкладки настроек.
- `build_settings_tab(parent, context, import_formats)` — метод для построения интерфейса вкладки `Settings`. Эта вкладка позволяет управлять кошельками, обязательными расходами, backup и запуском аудита.
- `show_audit_report_dialog(report, parent)` — модальный диалог результата аудита с секциями `Errors`, `Warnings`, `Passed`.

`gui/controllers.py`

- `FinancialController` — класс управления бизнес-логикой приложения.
- `import_records(fmt, filepath, policy, force=False, dry_run=False)` — единая точка входа для dry-run и реального импорта операций.
- `import_mandatory(fmt, filepath)` — импорт шаблонов обязательных расходов с результатом `ImportResult`.
- `run_audit()` — запуск Data Audit Engine через use case и возврат `AuditReport`.
- `get_net_worth_timeline()` — net worth (KZT) на конец каждого месяца (Timeline Engine, только SQLite).
- `get_monthly_cashflow(start_date=None, end_date=None)` — доходы/расходы/cashflow по месяцам (исключая переводы).
- `get_cumulative_income_expense()` — накопительные суммы доходов и расходов по месяцам (исключая переводы).

`gui/exporters.py`

- `export_report(report, filepath, fmt)`.
- `export_mandatory_expenses(expenses, filepath, fmt)`.
- `export_records(records, filepath, fmt, initial_balance=0.0, transfers=None)`.
- `export_full_backup(filepath, wallets, records, mandatory_expenses, transfers, initial_balance=0.0)`.

`gui/importers.py`

- Legacy-обёртки над `utils/*` для обратной совместимости и unit-тестов.

`services/import_parser.py`

- `parse_import_file(path, force=False)` -> `ParsedImportData` (DTO/словарный слой, без записи в хранилище).
- Валидация ограничений: размер файла, row-limit, размер CSV-поля.

`services/import_service.py`

- `ImportService.import_file(path, force=False, dry_run=False)` — dry-run или реальный импорт операций; возвращает `ImportResult`.
- `ImportService.import_mandatory_file(path)` — импорт шаблонов обязательных расходов; возвращает `ImportResult`.
- Dry-run использует тот же parse/validation pipeline, но не пишет в SQLite.
- `Full Backup` сохраняет фиксированные `amount_kzt/rate_at_operation`; `Current Rate` пересчитывает значения.

`services/audit_service.py`

- `AuditService(repository)` — read-only сервис диагностики SQLite.
- `run()` — сканирует SQLite и выполняет 10 проверок целостности и консистентности.
- Все проверки возвращают `AuditFinding`, а при отсутствии нарушений формируют один `OK` finding на check.

`services/balance_service.py`

- `WalletBalance(wallet_id, name, currency, balance)` — immutable snapshot баланса кошелька.
- `CashflowResult(income, expenses, cashflow)` — immutable агрегат по периоду.
- `BalanceService(repository)` — read-only аналитика по `wallets` + `records`.
- `get_wallet_balance(wallet_id, date=None)` — баланс кошелька на дату или по полной истории.
- `get_wallet_balances(date=None)` — список балансов всех активных кошельков.
- `get_total_balance(date=None)` — суммарный баланс системы.
- `get_cashflow(start_date, end_date)` — доходы, расходы и net cashflow без double-counting transfer.
- `get_income(start_date, end_date)` — доходы за период без transfer.
- `get_expenses(start_date, end_date)` — расходы за период, включая `mandatory_expense`.

`services/timeline_service.py`

- `MonthlyNetWorth(month, balance)` — immutable snapshot net worth на конец месяца.
- `MonthlyCashflow(month, income, expenses, cashflow)` — immutable агрегат cashflow по месяцу.
- `MonthlyCumulative(month, cumulative_income, cumulative_expenses)` — immutable накопительные суммы по месяцам.
- `TimelineService(repository)` — read-only аналитика по timeline из `wallets` + `records`.
- `get_net_worth_timeline()` — net worth (KZT) на конец каждого месяца (включая transfer-пары, они нейтральны).
- `get_monthly_cashflow(start_date=None, end_date=None)` — доходы/расходы/cashflow по месяцам (исключая `transfer_id IS NOT NULL`).
- `get_cumulative_income_expense()` — накопительные доходы и расходы по месяцам (исключая `transfer_id IS NOT NULL`).

`app/finance_service.py`

- Протокол `FinanceService` для import-оркестратора (`ImportService`).
- Явно описывает методы импорта, rollback и нормализации идентификаторов.

`app/use_case_support.py`

- Общие helper'ы для сценариев use case без собственной доменной логики.

`gui/helpers.py`

- `open_in_file_manager(path)`.

`gui/controller_support.py`

- Вспомогательные структуры и helper'ы для GUI-контроллера (`RecordListItem`, list-building, import normalization).

### Utils

`utils/backup_utils.py`

- `compute_checksum(data)` — SHA256 для `data`.
- `export_full_backup_to_json(filepath, wallets, records, mandatory_expenses, transfers, initial_balance=0.0, readonly=True, storage_mode="unknown")`.
- `import_full_backup_from_json(filepath, force=False)`.

`utils/csv_utils.py`

- `report_to_csv(report, filepath)`.
- `report_from_csv(filepath)`.
- `export_records_to_csv(records, filepath, initial_balance=0.0, transfers=None)`.
- `import_records_from_csv(filepath, policy, currency_service, wallet_ids=None)`.
- `export_mandatory_expenses_to_csv(expenses, filepath)`.
- `import_mandatory_expenses_from_csv(filepath, policy, currency_service)`.

`utils/excel_utils.py`

- `report_to_xlsx(report, filepath)`.
- `report_from_xlsx(filepath)`.
- `export_records_to_xlsx(records, filepath, initial_balance=0.0, transfers=None)`.
- `import_records_from_xlsx(filepath, policy, currency_service, wallet_ids=None)`.
- `export_mandatory_expenses_to_xlsx(expenses, filepath)`.
- `import_mandatory_expenses_from_xlsx(filepath, policy, currency_service)`.

`utils/tabular_utils.py`

- Общие helper'ы для CSV/XLSX row-building, type label formatting и rate resolver.

`utils/pdf_utils.py`

- `report_to_pdf(report, filepath)`.

`utils/charting.py`

- `aggregate_expenses_by_category(records)`.
- `aggregate_daily_cashflow(records, year, month)`.
- `aggregate_monthly_cashflow(records, year)`.
- `extract_years(records)`.
- `extract_months(records)`.

`utils/import_core.py`

- `norm_key(value)`.
- `as_float(value, default=None)`.
- `safe_type(value)`.
- `record_type_name(record)`.
- `parse_import_row(row, row_label, policy, get_rate, mandatory_only)`.

---

## 📁 Файловая структура

```text
project/
│
├── main.py                     # Точка входа приложения
├── config.py                   # Пути runtime SQLite и JSON import/export
├── bootstrap.py                # Инициализация SQLite + стартовая валидация
├── backup.py                   # Backup JSON и экспорт SQLite -> JSON
├── migrate_json_to_sqlite.py   # Миграция данных из JSON в SQLite
├── version.py                  # Версия приложения для snapshot metadata
├── data.json                   # JSON import/export/backup файл (опционально)
├── currency_rates.json         # Кэш курсов валют (use_online=True)
├── requirements.txt            # Runtime-зависимости
├── requirements-dev.txt        # Dev-зависимости (тесты, coverage)
├── pytest.ini                  # Настройки pytest
├── pyproject.toml              # Конфигурация проекта
├── README.md                   # Эта документация
├── README_EN.md                # Документация на английском
├── CHANGELOG.md                # История изменений
├── LICENSE                     # Лицензия
│
├── app/                        # Application layer
│   ├── __init__.py
│   ├── finance_service.py      # Протокол FinanceService для import-сервиса
│   ├── record_service.py       # Сервис записей
│   ├── services.py             # CurrencyService адаптер
│   ├── use_case_support.py     # Общие helper'ы для use cases
│   └── use_cases.py            # Сценарии использования
│
├── domain/                     # Domain layer
│   ├── __init__.py
│   ├── audit.py                # Модели и логика аудита
│   ├── records.py              # Записи
│   ├── reports.py              # Отчёты
│   ├── currency.py             # Доменный CurrencyService
│   ├── wallets.py              # Кошельки
│   ├── transfers.py            # Переводы
│   ├── validation.py           # Валидация дат и периодов
│   ├── errors.py               # Ошибки приложения
│   ├── import_policy.py        # Политики импорта
│   └── import_result.py        # Результаты импорта
│
├── infrastructure/             # Infrastructure layer
│   ├── repositories.py         # JSON-репозиторий
│   └── sqlite_repository.py    # SQLite-репозиторий
│
├── storage/                    # Абстракция storage и адаптеры JSON/SQLite
│   ├── __init__.py
│   ├── base.py                 # Базовый класс хранилища
│   ├── json_storage.py         # Адаптер JSON-хранилища
│   └── sqlite_storage.py       # Адаптер SQLite-хранилища
│
├── db/                         # SQL schema для SQLite
│   └── schema.sql
│
├── services/                   # Сервисный импортный слой
│   ├── __init__.py
│   ├── audit_service.py        # Сервис аудита
│   ├── balance_service.py      # Read-only сервис балансов и cashflow
│   ├── import_parser.py        # Парсер CSV/XLSX/JSON -> DTO
│   ├── import_service.py       # Оркестрация импорта через FinanceService
│   └── timeline_service.py     # Read-only сервис временных рядов
│
├── utils/                      # Импорт/экспорт и графики
│   ├── __init__.py
│   ├── backup_utils.py         # Резервное копирование данных
│   ├── import_core.py          # Валидатор импорта
│   ├── charting.py             # Графики и агрегации
│   ├── csv_utils.py
│   ├── excel_utils.py
│   ├── pdf_utils.py
│   └── tabular_utils.py        # Общие helper'ы CSV/XLSX
│
├── gui/                        # GUI слой (Tkinter)
│   ├── tabs/
│   │   ├── infographics_tab.py # Вкладка с информационными графиками
│   │   ├── operations_tab.py   # Вкладка с операциями и переводами
│   │   ├── reports_tab.py      # Вкладка с отчётами
│   │   └── settings_tab.py     # Вкладка с кошельками и обязательными расходами
│   │
│   ├── __init__.py
│   ├── tkinter_gui.py          # Основное GUI-приложение
│   ├── controller_support.py   # Вспомогательные GUI helper'ы
│   ├── helpers.py              # Помощники для GUI
│   ├── controllers.py          # Контроллеры GUI
│   ├── importers.py            # Legacy-обёртки импортеров (совместимость/тесты)
│   └── exporters.py            # Экспорт отчётов, записей, обязательных расходов и backup
│
└── tests/                      # Тесты
    ├── __init__.py
    ├── conftest.py             # Локальная tmp-fixture для стабильных тестов
    ├── test_audit_engine.py
    ├── test_balance_service.py
    ├── test_charting.py
    ├── test_csv.py
    ├── test_currency.py
    ├── test_excel.py
    ├── test_gui_exporters_importers.py
    ├── test_import_balance_contract.py
    ├── test_bootstrap_backup.py
    ├── test_bootstrap_migration_verification.py
    ├── test_migrate_json_to_sqlite.py
    ├── test_import_core.py
    ├── test_import_dry_run.py
    ├── test_import_parser.py
    ├── test_import_policy_and_backup.py
    ├── test_import_security.py
    ├── test_import_service.py
    ├── test_mandatory_ux.py
    ├── test_pdf.py
    ├── test_records.py
    ├── test_reports.py
    ├── test_repositories.py
    ├── test_schema_contracts.py
    ├── test_services.py
    ├── test_sqlite_runtime_storage.py
    ├── test_timeline_service.py
    ├── test_use_cases.py
    ├── test_validation.py
    ├── test_transfer_integrity.py
    ├── test_transfer_order_sqlite.py
    ├── test_wallet_phase1.py
    ├── test_wallet_phase2.py
    ├── test_wallet_phase3.py
    ├── test_phase33_immutable_repo_service.py
    └── test_phase4_import_export.py
```

---

## 🧪 Тесты

### Запуск

```bash
# Перейти в директорию проекта
cd "Проект ФУ/project"

# Установка dev-зависимостей (если не установлены)
pip install -r requirements-dev.txt

# Запуск всех тестов (в активированном venv)
python -m pytest

# С подробным выводом
python -m pytest -v

# Конкретный файл
python -m pytest tests/test_records.py -v

# Конкретный тест
python -m pytest tests/test_reports.py::test_report_total -v
```

### Покрытие

```bash
pip install -r requirements-dev.txt
python -m pytest --cov=. --cov-report=term-missing
python -m pytest --cov=. --cov-report=html
```

> **Примечание:** тесты ожидают, что `CurrencyService` по умолчанию использует локальные курсы (параметр `use_online=False`).

---

## 💱 Поддерживаемые валюты

Дефолтные курсы приложения:

| Валюта              | Код | Дефолтный курс | Описание        |
| ------------------- | --- | -------------- | --------------- |
| Казахстанский тенге | KZT | 1.0            | Базовая валюта  |
| Доллар США          | USD | 500.0          | 1 USD = 500 KZT |
| Евро                | EUR | 590.0          | 1 EUR = 590 KZT |
| Российский рубль    | RUB | 6.5            | 1 RUB = 6.5 KZT |

Если создать `CurrencyService(use_online=True)`, то курсы будут загружены с НБ РК и сохранены в `currency_rates.json`.

---

## 📄 Лицензия

MIT License — свободное использование, модификация и распространение.
