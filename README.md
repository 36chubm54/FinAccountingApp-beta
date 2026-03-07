# FinAccountingApp

Графическое и веб‑приложение для персонального финансового учёта с мультивалютностью, категориями и отчётами.

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

После запуска `python main.py` откроется окно с вкладками управления и блоком инфографики.

Вкладки и действия:

- `Infographics` — отображение инфографики (круговая диаграмма, гистограммы) с возможностью фильтрации по месяцу/году.
- `Operations` — управление записями и переводами (добавление, удаление, импорт/экспорт).
- `Reports` — генерация отчётов, экспорт.
- `Settings` — управление обязательными расходами и кошельками.

Инфографика:

- Круговая диаграмма расходов по категориям с фильтром месяца.
- Гистограмма доходов/расходов по дням месяца.
- Гистограмма доходов/расходов по месяцам года.

Доходы отображаются зелёным, расходы — красным. Для круговой диаграммы малые категории агрегируются в «Other». Список категорий в легенде прокручивается.

### Добавление дохода/расхода

1. Откройте вкладку `Operations`.
2. В блоке `Add operation` выберите тип операции (`Income` или `Expense`).
3. Укажите дату в формате `YYYY-MM-DD` (дата не может быть в будущем).
4. Введите сумму.
5. Укажите валюту (по умолчанию `KZT`).
6. Укажите категорию (по умолчанию `General`).
7. Нажмите `Save`.

Сумма конвертируется в базовую валюту `KZT` по текущим курсам сервиса валют. После добавления записи список автоматически обновляется.

### Добавление перевода

1. Откройте вкладку `Operations`.
2. В блоке `Add transfer` выберите тип перевода (`Transfer`).
3. Укажите дату в формате `YYYY-MM-DD` (дата не может быть в будущем).
4. Введите сумму.
5. Укажите источник и получатель кошельков.
6. Нажмите `Save`.

### Удаление записи

1. Откройте вкладку `Operations`.
2. Выберите запись из списка.
3. Нажмите `Delete Selected`. Появится сообщение об удалении с индексом записи или ID перевода.

### Удаление всех записей

1. Откройте вкладку `Operations`.
2. В блоке `List of operations` выберите запись из списка.
3. Нажмите `Delete All Records` и подтвердите удаление. Записи будут удалены без возможности восстановления, а список записей обновится.

### Inline-редактирование amount_kzt

1. Откройте вкладку `Operations`.
2. Выберите запись в списке.
3. Нажмите `Edit Amount KZT`.
4. Введите новое значение и нажмите `Save`.

Изменение выполняется через immutable-модель: создаётся новая версия записи, а `rate_at_operation` пересчитывается автоматически. Для transfer-связанных записей редактирование запрещено.

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

### Opening Balance in Filtered Reports

- `Initial balance` — начальный остаток всей истории; не зависит от фильтра.
- `Opening balance` — остаток на начало выбранного периода; вычисляется динамически.
- Для фильтра `YYYY` старт периода: `YYYY-01-01`.
- Для фильтра `YYYY-MM` старт периода: `YYYY-MM-01`.
- Для фильтра `YYYY-MM-DD` старт периода: указанная дата.
- Фильтр периода не может указывать на будущую дату (для всех форматов).

### Управление обязательными расходами

Во вкладке `Settings`, в блоке `Mandatory Expenses` доступны операции:

- `Add` — добавить обязательный расход.
- `Delete` — удалить выбранный.
- `Delete All` — удалить все.
- `Add to Records` — добавить выбранный расход в записи с указанной датой.
- Селектор формата файла для импорта/экспорта.
- `Import` — импорт обязательных расходов.
- `Export` — экспорт обязательных расходов.

Поля обязательного расхода:

- `Amount`, `Currency`, `Category` (по умолчанию `Mandatory`), `Description` (обязательно), `Period` (`daily`, `weekly`, `monthly`, `yearly`).

Импорт/экспорт обязательных расходов:

- Импорт: `CSV`, `XLSX`.
- Экспорт: `CSV`, `XLSX`.
- Поле `date` для шаблонов `mandatory_expenses` не хранится и не экспортируется.

### Импорт финансовых записей

Импорт выполняется через `Import` во вкладке `Operations`.

Архитектура импорта:

- `ImportService -> FinancialController (FinanceService) -> RecordRepository/Storage`.
- Импорт не создаёт записи напрямую через `JsonStorage/SQLiteStorage`.
- Переводы создаются только через `create_transfer(...)` сервиса (инвариант `1 transfer = 2 record` сохраняется).
- Импорт выполняется как атомарная сервисная транзакция: при ошибке выполняется rollback к снимку состояния.
- Для `Full Backup` сохраняются исходные `amount_kzt` и `rate_at_operation` из файла.
- Для `Current Rate` применяется пересчёт через `CurrencyService.get_rate(...)`.
- В parser-слое действуют лимиты безопасности (размер файла, число строк, размер CSV-поля).
- `initial_balance` в импортируемом файле допускается только один раз. Повторные строки считаются ошибкой и импорт откатывается.
- `wallet_id` в импортируемых данных должен быть целым положительным числом (без дробной части).
- Нечисловые и нефинитные значения (`NaN`, `inf`) в числовых полях импорта отклоняются.

Форматы:

- `JSON`, `CSV`, `XLSX`.
- Pipeline импорта: `parser -> domain validation -> SQLite transaction -> commit / rollback`.
- Все существующие runtime-данные заменяются данными из файла внутри транзакции SQLite.

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

Все режимы выполняют построчную валидацию и формируют отчёт:
`(imported, skipped, errors)`.

### Backup

Полный backup реализован в формате `JSON` в двух вариантах:

- `Snapshot backup` (по умолчанию):
  - корень: `meta` + `data`;
  - `meta.readonly=true`, `meta.checksum` (SHA256 от `data`);
  - checksum считается детерминированно по `json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
- `Technical backup` (`readonly=False`):
  - legacy-совместимый JSON без `meta` и без checksum;
  - используется для обычного pipeline без readonly-ограничения.
- Вкладка `Settings` содержит кнопки:
  - `Export Full Backup`
  - `Import Full Backup`
- Импорт `readonly` snapshot требует `force=True` (или подтверждение force в UI).

Backup восстанавливает:

- кошельки с полями `id/name/currency/balance`;
- все записи с полями `type/date/wallet_id/transfer_id/category/amount_original/currency/rate_at_operation/amount_kzt/category/description`;
- все обязательные расходы с `description/period`;
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

Пути резолвятся относительно каталога `project`, поэтому `finance.db` и `data.json` создаются внутри `project` даже при запуске из другой папки.

Инициализация происходит через `bootstrap.py`:

- приложение всегда использует SQLite как runtime storage;
- если `finance.db` отсутствует, база создаётся автоматически и schema инициализируется при старте;
- при старте обеспечивается наличие системного кошелька;
- выполняется проверка внутренней целостности SQLite:
  `PRAGMA foreign_key_check`, корректность связок transfer (`ровно 2 записи: income+expense`),
  отсутствие orphan records и CHECK-like нарушений;
- JSON bootstrap и работа приложения напрямую с `data.json` удалены.

Поведение SQLite по идентификаторам:

- Для рабочих операций `INSERT` выполняется без ручной передачи `id`; `id` генерируется SQLite.
- Для сценариев полной замены данных (`replace_all_data`, импорт backup, нормализация после импорта) выполняется переиндексация сущностей в диапазон `1..N`.
- При такой переиндексации ссылки (`wallet_id`, `transfer_id`, `from_wallet_id`, `to_wallet_id`) ремапятся атомарно, чтобы сохранить целостность связей.
- После очистки таблиц сбрасывается `sqlite_sequence`, чтобы новые записи снова начинались с `1`.
- Проверка равенства данных до/после импорта должна выполняться по бизнес-полям и инвариантам, а не по конкретным значениям `id`.

Формат:

```json
{
  "records": [
    {
      "id": 1,
      "type": "income",
      "date": "2025-01-15",
      "amount_original": 700.0,
      "currency": "USD",
      "rate_at_operation": 500.0,
      "amount_kzt": 350000.0,
      "category": "Зарплата",
      "description": ""
    },
    {
      "id": 2,
      "type": "expense",
      "date": "2025-01-16",
      "amount_original": 25000.0,
      "currency": "KZT",
      "rate_at_operation": 1.0,
      "amount_kzt": 25000.0,
      "category": "Продукты",
      "description": ""
    },
    {
      "id": 3,
      "type": "mandatory_expense",
      "date": "2025-01-20",
      "amount_original": 300.0,
      "currency": "USD",
      "rate_at_operation": 500.0,
      "amount_kzt": 150000.0,
      "category": "Mandatory",
      "description": "Monthly rent",
      "period": "monthly"
    },
    {
      "id": 4,
      "type": "expense",
      "date": "2026-02-20",
      "wallet_id": 1,
      "transfer_id": 1,
      "amount_original": 5000.0,
      "currency": "KZT",
      "rate_at_operation": 1.0,
      "amount_kzt": 5000.0,
      "category": "Transfer",
      "description": ""
    },
    {
      "id": 5,
      "type": "income",
      "date": "2026-02-20",
      "wallet_id": 2,
      "transfer_id": 1,
      "amount_original": 5000.0,
      "currency": "KZT",
      "rate_at_operation": 1.0,
      "amount_kzt": 5000.0,
      "category": "Transfer",
      "description": ""
    }
  ],
  "mandatory_expenses": [
    {
      "id": 1,
      "wallet_id": 1,
      "transfer_id": null,
      "amount_original": 300.0,
      "currency": "USD",
      "rate_at_operation": 500.0,
      "amount_kzt": 150000.0,
      "category": "Mandatory",
      "description": "Monthly rent",
      "period": "monthly"
    }
  ],
  "transfers": [
    {
      "id": 1,
      "from_wallet_id": 1,
      "to_wallet_id": 2,
      "date": "2026-02-20",
      "amount_original": 5000.0,
      "currency": "KZT",
      "rate_at_operation": 1.0,
      "amount_kzt": 5000.0,
      "description": ""
    }
  ]
}
```

---

## 🏗️ Архитектура проекта

Проект следует слоистой архитектуре:

- `domain/` — бизнес‑модели и правила (записи, отчёты, валидация дат и периодов, валюты, кошельки, transfers).
- `app/` — сценарии использования (use cases) и адаптер сервиса валют.
- `infrastructure/` — хранилище данных (JSON‑репозиторий).
- `infrastructure/` — JSON и SQLite реализации `RecordRepository`.
- `storage/` — абстракция хранилища и адаптеры JSON/SQLite.
- `db/` — SQL-схема для SQLite.
- `bootstrap.py` — инициализация SQLite и стартовая валидация.
- `backup.py` — backup JSON и экспорт SQLite -> JSON.
- `config.py` — флаг и пути storage.
- `utils/` — импорт/экспорт и подготовка данных для графиков.
- `gui/` — GUI слой (Tkinter).
- `web/` — автономное веб-приложение.

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

`domain/errors.py`

- `DomainError` — ошибка домена (выбрасывается при нарушении доменных инвариантов).

`domain/import_policy.py`

- `ImportPolicy` — import policy (enum).

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
- `grouped_by_category()` — группировка по категориям.
- `sorted_by_date()` — сортировка по дате.
- `net_profit_fixed()` — чистая прибыль по фиксированным курсам.
- `monthly_income_expense_rows(year=None, up_to_month=None)` — агрегаты по месяцам.
- `monthly_income_expense_table(year=None, up_to_month=None)` — таблица по месяцам.
- `as_table(summary_mode="full"|"total_only")` — табличный вывод.
- `to_csv(filepath)` и `from_csv(filepath)` — экспорт отчёта и backward-compatible импорт.

`domain/wallets/py`

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

- `CreateIncome.execute(date, wallet_id, amount, currency, category)`.
- `CreateExpense.execute(date, wallet_id, amount, currency, category)`.
- `GenerateReport.execute(wallet_id=None)` → `Report` с учётом начального остатка.
- `CreateWallet.execute(name, currency, initial_balance, allow_negative=False)` — создание нового кошелька.
- `GetWallets.execute()` — все кошельки.
- `GetActiveWallets.execute()` — активные кошельки.
- `SoftDeleteWallet.execute(wallet_id)` — безопасный soft delete.
- `CalculateWalletBalance.execute(wallet_id)` — вычисление баланса кошелька.
- `CalculateNetWorth.execute_fixed()` — вычисление чистых активов по фиксированным курсам.
- `CalculateNetWorth.execute_current()` — вычисление чистых активов по текущим курсам.
- `CreateTransfer.execute(from_wallet_id, to_wallet_id, transfer_date, amount_original, currency, description, comission_amount, comission_currency)` — создание перевода между кошельками.
- `DeleteTransfer.execute(transfer_id)` — каскадное удаление transfer-агрегата.
- `DeleteRecord.execute(index)`.
- `DeleteAllRecords.execute()`.
- `ImportFromCSV.execute(filepath)` — импорт и полная замена записей (CSV, `ImportPolicy.FULL_BACKUP`).
- `CreateMandatoryExpense.execute(amount, currency, category, description, period)`.
- `GetMandatoryExpenses.execute()`.
- `DeleteMandatoryExpense.execute(index)`.
- `DeleteAllMandatoryExpenses.execute()`.
- `AddMandatoryExpenseToReport.execute(index, date)`.

`app/record_service.py`

- `RecordService.update_amount_kzt(record_id, new_amount_kzt)` — безопасное обновление суммы через immutable-модель и repository replace.

### Infrastructure

`infrastructure/repositories.py`

- `RecordRepository` — интерфейс репозитория.
- `JsonFileRecordRepository(file_path="data.json")` — JSON‑репозиторий для backup/import/export сценариев.

`infrastructure/sqlite_repository.py`

- `SQLiteRecordRepository(db_path="finance.db")` — SQLite-реализация `RecordRepository` для сервисного слоя.

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
- `build_operations_tab(parent, context, import_formats)` — метод для построения интерфейса вкладки `Operations`. Эта вкладка поддерживает добавление и удаление записей, а также редактирование валютных значений с математическим пересчётом курса. Также поддерживает создание переводов импорт/экспорт записей.

`gui/tabs/reports_tab.py`

- `ReportTabContext` — контекст вкладки отчетов.
- `build_reports_tab(parent, context)` — метод для построения интерфейса вкладки `Reports`. Эта вкладка поддерживает 2 режима итогов:
  - `По курсу операции`
  - `По текущему курсу`
- Курсовая разница выводится отдельной строкой (`FX Difference`).
- Месячные агрегаты и графики всегда считаются в фиксированном режиме (`amount_kzt`).

`gui/tabs/settings_tab.py`

- `SettingsTabContext` — контекст вкладки настроек.
- `build_settings_tab(parent, context, import_formats)` — метод для построения интерфейса вкладки `Settings`. Эта вкладка позволяет управлять кошельками и обязательными расходами.

`gui/controllers`

- `FinanceController` — класс управления бизнес-логикой приложения.

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

- `ImportService.import_file(path, force=False)` — импорт операций через методы `FinancialController`.
- `ImportService.import_mandatory_file(path)` — импорт шаблонов обязательных расходов через сервис.
- `Full Backup` сохраняет фиксированные `amount_kzt/rate_at_operation`; `Current Rate` пересчитывает значения.

`app/finance_service.py`

- Протокол `FinanceService` для import-оркестратора (`ImportService`).
- Явно описывает методы импорта, rollback и нормализации идентификаторов.

`gui/helpers.py`

- `open_in_file_manager(path)`.

### Utils

`utils/backup_utils.py`

- `compute_checksum(data)` — SHA256 для `data`.
- `export_full_backup_to_json(filepath, wallets, records, mandatory_expenses, transfers, initial_balance=0.0, readonly=True)`.
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
├── config.py                   # Конфигурация storage (SQLite/JSON)
├── bootstrap.py                # Инициализация SQLite + стартовая валидация
├── backup.py                   # Backup JSON и экспорт SQLite -> JSON
├── migrate_json_to_sqlite.py   # Миграция данных из JSON в SQLite
├── data.json                # JSON import/export/backup файл (опционально)
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
│   └── use_cases.py            # Сценарии использования
│
├── domain/                     # Domain layer
│   ├── __init__.py
│   ├── records.py              # Записи
│   ├── reports.py              # Отчёты
│   ├── currency.py             # Доменный CurrencyService
│   ├── wallets.py              # Кошельки
│   ├── transfers.py            # Переводы
│   ├── validation.py           # Валидация дат и периодов
│   ├── errors.py               # Ошибки приложения
│   └── import_policy.py        # Политики импорта
│
├── infrastructure/             # Infrastructure layer
│   ├── repositories.py         # JSON-репозиторий
│   └── sqlite_repository.py    # SQLite-репозиторий
│
├── storage/                    # Абстракция storage и адаптеры JSON/SQLite
│   ├── __init__.py
│   ├── base.py
│   ├── json_storage.py
│   └── sqlite_storage.py
│
├── db/                         # SQL schema для SQLite
│   └── schema.sql
│
├── services/                   # Сервисный импортный слой
│   ├── __init__.py
│   ├── import_parser.py        # Парсер CSV/XLSX/JSON -> DTO
│   └── import_service.py       # Оркестрация импорта через FinanceService
│
├── utils/                      # Импорт/экспорт и графики
│   ├── __init__.py
│   ├── backup_utils.py         # Резервное копирование данных
│   ├── import_core.py          # Валидатор импорта
│   ├── charting.py             # Графики и агрегации
│   ├── csv_utils.py
│   ├── excel_utils.py
│   └── pdf_utils.py
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
│   ├── helpers.py              # Помощники для GUI
│   ├── controllers.py          # Контроллеры GUI
│   ├── importers.py            # Legacy-обёртки импортеров (совместимость/тесты)
│   └── exporters.py            # Экспорт отчётов, записей, обязательных расходов и backup
│
└── tests/                      # Тесты
    ├── __init__.py
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
    ├── test_import_parser.py
    ├── test_import_policy_and_backup.py
    ├── test_import_security.py
    ├── test_import_service.py
    ├── test_pdf.py
    ├── test_records.py
    ├── test_reports.py
    ├── test_repositories.py
    ├── test_services.py
    ├── test_sqlite_runtime_storage.py
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
