# FinAccountingApp

Графическое приложение для персонального финансового учёта с мультивалютностью, импортом/экспортом, бюджетами, долгами, активами и целями.

Текущий релиз `v1.10.1` закрепляет `Assets / Goals / Dashboard` как стабильный слой: поверх `v1.10.0` он усиливает import/backup/migration paths, исправляет rollback и нормализацию связей, делает batch/file writes атомарнее и жёстче валидирует битые JSON payloads до записи в хранилище.

## 🚀 Быстрый старт

### Требования

- Python `3.11+`
- `pip`

### Установка

```bash
cd "Проект ФУ/project"

python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

# Linux/macOS
source .venv/bin/activate

# Базовые runtime-зависимости
pip install -r requirements.txt

# Опционально: PDF-экспорт
pip install -r requirements-pdf.txt
# или:
# pip install .[pdf]

# Dev-зависимости
pip install -r requirements-dev.txt
```

### Запуск приложения

```bash
python main.py
```

Приложение запускает Tkinter GUI поверх SQLite runtime-storage. Основные вкладки могут достраиваться лениво, а post-startup maintenance выполняется после первого показа окна.

## ✨ Основные возможности

- Учёт доходов, расходов, обязательных платежей и переводов между кошельками
- Мультивалютные записи с пересчётом в базовую валюту `KZT`
- Отчёты с fixed-rate и current-rate итогами, grouped view и экспортом в `CSV` / `XLSX` / `PDF`
- Финансовая аналитика: `net worth`, cashflow, category breakdown, monthly summary
- Бюджеты по категориям с live progress и pace tracking
- Учёт долгов и ссуд с историей погашений и write-off сценариями
- Distribution System для monthly net-income allocation
- Wealth layer: `Assets`, `Goals`, wealth `Dashboard`
- Full backup / import / migration для `JSON` ↔ `SQLite`
- Read-only Data Audit Engine для проверки консистентности данных

## 🖥️ Вкладки приложения

- `Infographics` — быстрый визуальный обзор расходов и cashflow по дням/месяцам
- `Operations` — добавление, редактирование, удаление, импорт и экспорт операций
- `Reports` — генерация отчётов, grouped summary, wallet/category filters, export
- `Analytics` — метрики за период: `net worth`, savings rate, burn rate, monthly summary
- `Dashboard` — wealth overview: `Assets`, `Goals`, allocation, compact net-worth trend
- `Budget` — лимиты по категориям и live tracking исполнения
- `Debts` — долги и ссуды: создание, погашение, write off, close, history, progress
- `Distribution` — monthly net-income distribution и frozen snapshots
- `Settings` — кошельки, mandatory expenses, backup/import, audit

## 🏗️ Архитектура в 5 слоях

| Слой | Ответственность |
| --- | --- |
| `domain` | Immutable-модели и бизнес-правила: records, wallets, budgets, debts, assets, goals, reports |
| `app` | Use cases и orchestration между GUI, сервисами и репозиторием |
| `services` | Специализированные сценарии: import, audit, analytics, budget/debt/distribution/wealth logic |
| `infrastructure` + `storage` | SQLite/JSON persistence, schema bootstrap, repository/storage adapters |
| `gui` | Tkinter UI, controller layer, exporters/import preview dialogs, tab composition |

Что ещё важно:

- `utils` — форматы импорта/экспорта, PDF/XLSX helpers, money helpers, charting
- `tests` — regression и contract coverage для domain/app/services/gui/import-export flows

## 🔌 Ключевые точки расширения

### Основные entry points

| Точка | Когда использовать |
| --- | --- |
| `gui.controllers.FinancialController` | Главная точка входа для GUI и интеграций верхнего уровня |
| `services.import_service.ImportService` | Реальный import pipeline: dry-run, validation, commit |
| `services.audit_service.AuditService` | Read-only проверка целостности SQLite-данных |
| `services.balance_service.BalanceService` | Балансы кошельков, total balance, cashflow |
| `services.metrics_service.MetricsService` | Savings rate, burn rate, monthly/category analytics |
| `services.budget_service.BudgetService` | Budget CRUD и live tracking |
| `services.debt_service.DebtService` | Debt/loan lifecycle |
| `services.distribution_service.DistributionService` | Monthly distribution и frozen rows |
| `infrastructure.sqlite_repository.SQLiteRecordRepository` | Основной runtime repository |
| `storage.sqlite_storage.SQLiteStorage` | Низкоуровневый SQLite adapter / schema bootstrap |

### Import / backup entry points

| Точка | Назначение |
| --- | --- |
| `FinancialController.import_records(...)` | Основной app-level импорт из GUI/controller |
| `ImportService.import_file(...)` | Основной pipeline импорта операций |
| `utils.backup_utils.export_full_backup_to_json(...)` | Low-level full backup export |
| `utils.backup_utils.import_full_backup_from_json(...)` | Low-level backup parser, возвращает `ImportedBackupData` |
| `migrate_json_to_sqlite.py` | Полная миграция JSON payload в SQLite |
| `backup.py` | Экспорт текущего SQLite state в backup / `data.json` |

### Важные developer-сценарии

- Добавление новой сущности обычно затрагивает `domain` → `repository/storage` → `app/use_cases` → `gui/controllers` → нужную вкладку
- Новые read-only метрики лучше добавлять в `services/*_service.py`, а не в GUI
- Новые форматы/варианты импорта лучше подключать через `ImportService` и `utils/import_core.py`
- Если меняется schema, нужно синхронно обновлять `db/schema.sql`, bootstrap/migration flow и regression tests

## 🧪 Тесты

### Запуск

```bash
pytest
```

```bash
pytest --cov=. --cov-report=term-missing
```

### Что покрыто

- domain-модели и validation rules
- use cases и controller flows
- import/export contracts (`CSV`, `XLSX`, `JSON`, backup)
- SQLite runtime storage, bootstrap и migration
- GUI-level regression tests для критичных вкладок и exporters

## 💾 Импорт / backup / migration

### Import

- Pipeline: `parse -> dry-run validation -> user confirmation -> SQLite transaction`
- Поддерживаются `CSV`, `XLSX`, `JSON`
- Для `JSON` full backup восстанавливаются runtime-сущности, включая `budgets`, `debts`, `debt_payments`, distribution/wealth payloads, если подсистемы поддерживаются репозиторием
- Для readonly snapshot требуется `force=True`
- Для `JSON` под `ImportPolicy.CURRENT_RATE` fast bulk-replace path тоже разрешён, если репозиторий его поддерживает
- `v1.10.1` усиливает раннюю валидацию import payload: битые ссылочные связи, дубликаты `wallet.id`, несколько `system` wallets и невалидные/дублированные `distribution_snapshots` теперь отсекаются раньше

### Backup

- Full backup хранится в `JSON`
- Базовый low-level parser: `import_full_backup_from_json(...)`
- `import_backup(...)` оставлен только как deprecated compatibility wrapper
- JSON export и backup-copy paths записываются atomically через temporary file + `fsync` + `os.replace`
- `requirements-pdf.txt` нужен только для PDF-экспорта, не для базового runtime

### Migration

```bash
python migrate_json_to_sqlite.py --dry-run
python migrate_json_to_sqlite.py --json-path data.json --sqlite-path finance.db
```

- Скрипт переносит JSON payload в SQLite в одной явной транзакции
- Pre-schema compatibility поддерживает старые SQLite БД, где таблица `records` ещё без `related_debt_id`
- Migration и bootstrap должны идти в паре с актуальным `db/schema.sql`

## 🧭 Ссылка на подробную архитектуру

Сейчас README оставлен компактным и ориентированным на релиз/use cases.  
Подробная техническая карта слоёв, runtime-flows и модулей вынесена в `docs/architecture.md`.

## 💱 Поддерживаемые валюты

- `KZT` — базовая валюта
- `RUB`
- `USD`
- `EUR`

Курсы обновляются через `CurrencyService`; offline-mode сохраняет последнее доступное состояние.

## 📄 Лицензия

Проект распространяется под лицензией `MIT`. См. `LICENSE`.
