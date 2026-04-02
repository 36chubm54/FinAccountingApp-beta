# FinAccountingApp

Графическое приложение для персонального финансового учёта с мультивалютностью, категориями и отчётами.

Текущий релиз `v1.9.0` добавляет встроённый учёт долгов и ссуд: отдельную вкладку `Debts`, историю погашений/списаний, debt-aware backup/import/export, а также учёт открытых обязательств в `net worth` и audit/report flows.

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
В нижней части окна всегда видна статус-строка с версией приложения, статусом валютных курсов и переключателем `Online`, который можно включать и выключать без перезапуска.
Основные вкладки теперь могут достраиваться лениво, а post-startup maintenance выполняется уже после первого показа окна, чтобы уменьшить блокировку запуска.

Вкладки и действия:

- `Infographics` — отображение инфографики (круговая диаграмма, гистограммы) с возможностью фильтрации по месяцу/году.
- `Operations` — управление записями и переводами (добавление, редактирование, удаление, импорт/экспорт).
- `Reports` — генерация отчётов, экспорт.
- `Analytics` — финансовая аналитика за произвольный период (dashboard, категории, помесячный отчёт).
- `Budget` — бюджеты по категориям с произвольным диапазоном дат, pace-tracking и live progress.
- `Debts` — учёт долгов и ссуд: создание, погашение, списание, закрытие, история и progress bar.
- `Distribution` — структура распределения net income по месяцам с фиксацией строк и историей snapshot'ов.
- `Settings` — управление обязательными расходами и кошельками.

Инфографика:

- Круговая диаграмма расходов по категориям с фильтром месяца.
- Гистограмма доходов/расходов по дням месяца.
- Гистограмма доходов/расходов по месяцам года.

Доходы отображаются зелёным, расходы — красным. Для круговой диаграммы малые категории агрегируются в «Other». Список категорий в легенде прокручивается. Исключены записи с категорией "Transfer" для повышения точности анализа и консистентности.

### Analytics tab

Финансовая аналитика за произвольный период.

- **Dashboard** — ключевые метрики: net worth, savings rate, burn rate, avg monthly income, avg monthly expenses, year income, year expense, cost per day/hour/minute.
- **Net Worth Timeline** — линейный график накопленного капитала по месяцам.
- **Category Breakdown** — расходы и доходы по категориям (таблица + pie chart расходов).
- **Monthly Report** — таблица доходов, расходов, сальдо и нормы сбережений по месяцам.

Фильтр периода задаётся в формате `YYYY-MM-DD` в полях `From` / `To`. Переводы исключаются из расчётов.
Для `Dashboard` показатель net worth теперь берётся на дату `To`, а не как текущее значение на момент открытия вкладки.
В Dashboard появился tooltip `ⓘ` с кратким объяснением формул метрик.
`Year expense` считается как сумма расходов за календарный год до выбранной конечной даты, а `Cost per day/hour/minute` строится именно от этого year-to-date расхода, а не от annualized burn rate.

> **Примечание:** После запуска приложения автоматически применяются обязательные платежи с выводом детального GUI-сообщения.
> Если ранее был сохранён online-режим, приложение восстановит его при старте и попытается обновить курсы в фоне.

### Budget tab

Планирование и контроль бюджетов по категориям за произвольный период.

- Форма `New Budget`: `Category`, `From`, `To`, `Limit (KZT)`, флаг `Include mandatory expenses`.
- Таблица бюджетов показывает `Category`, `Period`, `Limit`, `Spent`, `Remaining`, `Usage %`, `Pace`, `Status`, `Include mandatory`.
- Статусы pace: `on_track`, `overpace`, `overspent`.
- Статусы периода: `future`, `active`, `expired`.
- Ниже таблицы отображается progress canvas:
  цветная полоса = потраченная доля бюджета, синяя вертикаль = доля прошедшего времени.
- Для одной категории можно создавать несколько бюджетов, но без пересечения диапазонов дат.

### Distribution tab

Структура распределения месячного net income и просмотр истории по месяцам.

- Левая панель `Distribution Structure` управляет top-level item/subitem структурой с процентами и группами.
- Правая таблица `Distribution Table` показывает `Month`, `Fixed`, `Net income` и рассчитанные суммы по item/subitem колонкам.
- Кнопка `Fix Row` фиксирует или снимает фиксацию строки месяца; auto-fixed закрытые месяцы защищены от ручного unfix.
- При запросе frozen rows сервис автоматически фиксирует закрытые прошедшие месяцы.
- Валидация требует, чтобы top-level item'ы суммарно давали `100%`, а subitem'ы внутри item'а тоже давали `100%`, если они заданы.

### Debts tab

Учёт долгов (`Debt`) и выданных ссуд (`Loan`) с отдельной историей и прогрессом закрытия.

- Форма `New Debt / Loan`: `Kind`, `Contact`, `Amount`, `Date`, `Wallet`, `Description`.
- Таблица показывает `Contact`, `Kind`, `Total`, `Remaining`, `Status`, `Created`.
- Действия для выбранного долга: `Pay`, `Write off`, `Close`, `Delete`, `Refresh`.
- `Write off` уменьшает остаток долга без движения баланса кошелька.
- `Delete` удаляет debt-card и debt payment history, но не откатывает связанные income/expense records и не пересчитывает прошлые wallet balances.
- Прогресс-бар и блок `History` показывают уже погашенную, списанную и оставшуюся части долга.

### Добавление дохода/расхода

1. Откройте вкладку `Operations`.
2. В блоке `Add operation` выберите тип операции (`Income` или `Expense`).
3. Укажите дату в формате `YYYY-MM-DD` (дата не может быть в будущем и ранее UNIX-времени).
4. Введите сумму.
5. Укажите валюту (по умолчанию `KZT`).
6. Укажите категорию (по умолчанию `General`).
   Поле категории — редактируемый `Combobox`: для `Income` предлагаются известные категории доходов, для `Expense` — категории расходов; ручной ввод также разрешён.
7. При необходимости заполните `Description`.
8. Нажмите `Save`.

Сумма конвертируется в базовую валюту `KZT` по текущим курсам сервиса валют. После добавления записи список автоматически обновляется.

### Добавление перевода

1. Откройте вкладку `Operations`.
2. В блоке `Transfer` выберите `From wallet` и `To wallet`.
3. Укажите дату в формате `YYYY-MM-DD` (дата не может быть в будущем и ранее UNIX-времени).
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

Изменение выполняется через immutable-модель: создаётся новая версия записи, `rate_at_operation` пересчитывается автоматически, а `description` остаётся необязательным. Дата валидируется (формат `YYYY-MM-DD`, не в будущем и не ранее UNIX-времени), кошелёк должен быть активным. Для transfer-связанных записей и записей с категорией `"Transfer"` редактирование запрещено.

### Генерация отчёта

1. Откройте вкладку `Reports`.
2. Введите фильтры (опционально):
    - `Period` — начало периода (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`).
    - `Period end` — конец периода (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`).
    - `Category` — фильтр по категории.
3. Выберите один кошелёк для генерации отчёта по нему или все кошельки.
4. При необходимости включите `Group by category` — группировка по категориям (double-click по категории открывает её детализацию, кнопка `Back` возвращает к сводке).
5. Выберите `Totals mode`:
    - `On fixed rate` — итоги по фиксированным `amount_kzt` (курс операции).
    - `On current rate` — итоги по текущим курсам (`CurrencyService`).
6. Нажмите `Generate`.

Справа отображается блок «Monthly summary» (агрегаты доходов/расходов по месяцам).

Экспорт отчёта:

- Форматы: `CSV`, `XLSX`, `PDF`.
- В заголовке отчёта указывается диапазон периода:
  `Transaction statement (<start_date> - <end_date>)`.
- Если `Period end` не указан, в качестве конца периода используется текущая дата.
- Кроме основных записей, в `XLSX` добавляется лист `Yearly Report` с помесячной сводкой. Лист `By Category` создаётся только когда группировка действительно добавляет отдельную сводку, а не дублирует уже отфильтрованный отчёт.
- `XLSX` теперь оформляется как readable export: стилизованные header/total rows, `freeze panes`, `auto filter`, auto-width колонок и числовые ячейки вместо строковых сумм.
- В `PDF` помесячная сводка остаётся, а после основной выписки добавляются таблицы с разбивкой по категориям; если отчёт уже отфильтрован до одной категории, дублирующий grouped-блок не выводится.
- При включённом `Group by category` экспорт summary-вида выполняется как grouped report в `CSV` / `XLSX` / `PDF`.

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
- `get_total_balance(date=None)` — общий баланс системы (net worth) с учётом открытых debts/loans
- `get_cashflow(start_date, end_date)` — доходы, расходы и cashflow за период
- `get_income(start_date, end_date)` — доходы за период
- `get_expenses(start_date, end_date)` — расходы за период

Сервис строго только читает данные — база никогда не изменяется.
Переводы (`category='Transfer'`) исключаются из cashflow-расчётов во избежание двойного счёта.

### Timeline Engine

Аналитический сервис для построения исторической динамики финансов.

| Метод                                        | Описание                                |
| -------------------------------------------- | --------------------------------------- |
| `get_net_worth_timeline()`                   | Net worth (KZT) на конец каждого месяца |
| `get_monthly_cashflow(start_date, end_date)` | Доходы, расходы, сальдо по месяцам      |
| `get_cumulative_income_expense()`            | Накопительные суммы доходов и расходов  |

Все методы read-only. Переводы (`transfer_id IS NOT NULL`) исключаются из cashflow-расчётов,
чтобы избежать двойного счёта; в net worth включаются (expense + income = 0, нейтральны).
Стартовый баланс (`wallets.initial_balance`) учитывается в каждой точке timeline.

### Metrics Engine

Аналитический сервис для вычисления финансовых метрик на лету.

| Метод                                           | Описание                                             |
| ----------------------------------------------- | ---------------------------------------------------- |
| `get_savings_rate(start, end)`                  | Норма сбережений (%) за период                       |
| `get_burn_rate(start, end)`                     | Средний дневной расход (KZT)                         |
| `get_spending_by_category(start, end)`          | Расходы по категориям, сортировка по убыванию        |
| `get_income_by_category(start, end)`            | Доходы по категориям, сортировка по убыванию         |
| `get_top_expense_categories(start, end, top_n)` | Топ N категорий расходов                             |
| `get_monthly_summary(start, end)`               | Доходы, расходы, сальдо, норма сбережений по месяцам |

Все методы read-only. Переводы (`transfer_id IS NULL`) исключаются из всех расчётов.
Метрики вычисляются через SQL-агрегаты без промежуточного хранения.

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

- Через UI вкладки `Operations`: `CSV`, `XLSX`.
- На уровне контроллера/сервисов также поддерживается `JSON`.
- Pipeline импорта: `parser -> dry-run validation -> user confirmation -> SQLite transaction`.
- Для `CSV/XLSX` реальный импорт заменяет runtime-данные валидными строками из файла; ошибочные строки остаются только в отчёте импорта.
- Для readonly `JSON` snapshot требуется `force=True`; проверка readonly/checksum выполняется ещё до этапа commit.
- `JSON` full backup теперь может включать `budgets`, `distribution_items`, `distribution_subitems` и `distribution_snapshots`; при импорте они восстанавливаются в SQLite, если репозиторий поддерживает соответствующие подсистемы.
- Для `JSON` full backup структура распределения валидируется строго: битые item/subitem payload'ы не пропускаются молча, а прерывают импорт с ошибкой.

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
  - GUI-export полного backup из `Settings` помечает источник как `meta.storage="sqlite"`.
- Вкладка `Settings` содержит кнопки:
  - `Export Full Backup`
  - `Import Full Backup`
- Импорт `readonly` snapshot требует `force=True` (или подтверждение force в UI).

Backup восстанавливает:

- кошельки с полями `id/name/currency/balance`;
- все записи с полями `type/date/wallet_id/transfer_id/category/amount_original/currency/rate_at_operation/amount_kzt/category/description`;
- все обязательные расходы с `date/description/period`;
- структуру распределения: `distribution_items` и `distribution_subitems`;
- frozen `distribution_snapshots` с видимой раскладкой колонок и значениями;
- все переводы между кошельками.

Дополнительно:

- export в JSON теперь записывается atomically через временный файл + `os.replace`, чтобы не оставлять частично записанные backup-файлы;
- startup SQLite → JSON export использует уже замороженные distribution months и может пропускать auto-freeze внутри фонового export-потока.

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
Этот экспорт теперь сохраняет `mandatory_expenses.date`, `budgets`, структуру Distribution System и frozen `distribution_snapshots`.

Для работы со storage используется отдельный слой `storage/`:

- `storage/base.py` — контракт `Storage` (только data-access операции).
- `storage/json_storage.py` — JSON-адаптер только для import/export/backup сценариев.
- `storage/sqlite_storage.py` — `SQLiteStorage` на стандартном `sqlite3`.
- `db/schema.sql` — SQL-схема таблиц `wallets`, `records`, `transfers`, `mandatory_expenses`, `budgets`, `debts`, `debt_payments`, `distribution_*`.

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
  `wallets -> transfers -> debts -> records -> mandatory_expenses -> budgets -> debt_payments -> distribution_items -> distribution_subitems -> distribution_snapshots`;
- сохраняет существующие `id` (или строит mapping `old_id -> new_id` при авто-генерации);
- при записи заполняет precision-поля `*_minor` и `rate_at_operation_text`;
- для full backup строго валидирует `distribution_items` / `distribution_subitems` и прерывает миграцию на битом payload;
- валидирует целостность и сверяет балансы/`net worth`;
- делает `rollback` при любой ошибке или расхождении.
- безопасен к повторному запуску: если SQLite уже содержит эквивалентный набор данных, миграция пропускается без ошибки.

### Конфигурация runtime storage

В модуле `config.py` задаются пути:

- `SQLITE_PATH = "finance.db"`
- `JSON_PATH = "data.json"`
- `JSON_BACKUP_KEEP_LAST = 30` — сколько timestamped JSON-бэкапов хранить в `project/backups/` (старые удаляются при старте после создания нового).
- `LAZY_EXPORT_SIZE_THRESHOLD = 50 * 1024 * 1024` — порог размера SQLite (в байтах), после которого экспорт SQLite → JSON может выполняться в фоне.

Пути резолвятся относительно каталога `project`, поэтому `finance.db` и `data.json` создаются внутри `project` даже при запуске из другой папки.

Инициализация происходит через `bootstrap.py`:

- приложение всегда использует SQLite как runtime storage;
- если `finance.db` отсутствует, база создаётся автоматически и schema инициализируется при старте;
- при старте обеспечивается наличие системного кошелька;
- выполняется проверка внутренней целостности SQLite:
  `PRAGMA foreign_key_check`, корректность связок transfer (`ровно 2 записи: income+expense`),
  отсутствие orphan records и CHECK-like нарушений;
- после успешной проверки выполняется lazy export SQLite → `data.json`:
  экспорт запускается только если `data.json` отсутствует или устарел относительно `finance.db`;
  при большом размере БД экспорт может выполняться в background thread (не блокируя UI);
- post-startup maintenance может запускаться отдельно от `bootstrap_repository()` — это позволяет GUI сначала показать окно, а затем выполнить freeze/export/backup синхронизацию;
- JSON bootstrap и работа приложения напрямую с `data.json` удалены.

Поведение SQLite по идентификаторам:

- Для рабочих операций `INSERT` выполняется без ручной передачи `id`; `id` генерируется SQLite.
- Для сценариев полной замены данных (`replace_all_data`, импорт backup, нормализация после импорта) выполняется переиндексация сущностей в диапазон `1..N`.
- При такой переиндексации ссылки (`wallet_id`, `transfer_id`, `from_wallet_id`, `to_wallet_id`) ремапятся атомарно, чтобы сохранить целостность связей.
- После очистки таблиц сбрасывается `sqlite_sequence`, чтобы новые записи снова начинались с `1`.
- Проверка равенства данных до/после импорта должна выполняться по бизнес-полям и инвариантам, а не по конкретным значениям `id`.

Поведение SQLite по денежным полям:

- Для денежных значений сохраняются и `REAL`-колонки, и точные integer minor-units (`*_minor`).
- Для курсов дополнительно сохраняется текстовое представление `rate_at_operation_text`.
- `SQLiteStorage` автоматически добавляет и backfill'ит эти колонки для существующих баз.

---

## 🏗️ Архитектура проекта

Проект следует слоистой архитектуре:

- `domain/` — бизнес‑модели и правила (записи, бюджеты, долги/ссуды, отчёты, аудит данных, валидация дат и периодов, валюты, кошельки, transfers).
- `app/` — сценарии использования (use cases), включая запуск аудита, и адаптер сервиса валют.
- `infrastructure/` — JSON и SQLite реализации `RecordRepository`, включая debt/debt-payment persistence.
- `storage/` — абстракция хранилища и адаптеры JSON/SQLite.
- `db/` — SQL-схема для SQLite.
- `bootstrap.py` — инициализация SQLite и стартовая валидация.
- `backup.py` — backup JSON и экспорт SQLite -> JSON, включая `budgets`, `debts`, `debt_payments` и distribution payloads.
- `config.py` — пути runtime SQLite и JSON import/export.
- `services/` — сервисный слой для импорта, read-only аудита, бюджетов, долгов/ссуд и аналитики SQLite.
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
- Денежные поля и `rate_at_operation` нормализуются через `utils.money` при создании объекта.
- `Record.with_updated_amount_kzt(new_amount_kzt)` — возвращает новый экземпляр записи с пересчитанным `rate_at_operation` и money-quantization.
- `IncomeRecord` — доход.
- `ExpenseRecord` — расход.
- `MandatoryExpenseRecord` — обязательный расход с `description` и `period`.

`domain/budget.py`

- `Budget` — immutable-модель бюджета категории с диапазоном дат и лимитом.
- `BudgetResult` — live-результат трекинга: потрачено, остаток, usage/time percentage, pace/status.
- `BudgetStatus` — `future` / `active` / `expired`.
- `PaceStatus` — `on_track` / `overpace` / `overspent`.
- `compute_pace_status(...)` — вычисление pace-статуса по spent/limit/time.

`domain/debt.py`

- `DebtKind`, `DebtStatus`, `DebtOperationType` — enum'ы видов обязательств, состояний и debt-операций.
- `Debt` — immutable debt/loan-card с `total_amount_minor`, `remaining_amount_minor`, `created_at`, `closed_at`.
- `DebtPayment` — immutable запись погашения/списания с `record_id`, `operation_type`, `principal_paid_minor`, `is_write_off`.

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
- `display_records()` / `sorted_display_records()` — записи для отображения (transfer-ноги исключаются из отчётного UI).
- `sorted_by_date()` — сортировка по дате.
- `net_profit_fixed()` — чистая прибыль по фиксированным курсам.
- `monthly_income_expense_rows(year=None, up_to_month=None)` — агрегаты по месяцам.
- `to_csv(filepath)` и `from_csv(filepath)` — экспорт отчёта и backward-compatible импорт.

`domain/wallets.py`

- `Wallet` — кошелёк (`allow_negative`, `is_active`).

`domain/transfers.py`

- `Transfer` — агрегат перевода между кошельками.
- Денежные поля и курс автоматически нормализуются до money/rate scale.

`domain/validation.py`

- `parse_ymd(value)` — парсинг и валидация даты `YYYY-MM-DD`.
- `ensure_not_before_unix(date)` — запрет дат, ранее UNIX-времени.
- `ensure_not_future(date)` — запрет будущих дат.
- `ensure_valid_period(period)` — валидация периодов.
- `parse_report_period_start(value)` — валидация фильтра отчёта (`YYYY`/`YYYY-MM`/`YYYY-MM-DD`) и вычисление даты старта периода без будущих дат.
- `parse_report_period_end(value)` — валидация конца периода отчёта (`YYYY`/`YYYY-MM`/`YYYY-MM-DD`) и вычисление даты конца периода без будущих дат.

### Application

`app/services.py`

- `CurrencyService(rates=None, base="KZT", use_online=False)` — адаптер для доменного сервиса.
- При `use_online=True` на старте пытается загрузить курсы НБ РК и кэширует их в `currency_rates.json`.
- Поддерживает runtime-переключение через `set_online(enabled)`, флаг `is_online`, метку `last_fetched_at` и ручное обновление `refresh_rates()`.
- В GUI online-режим управляется глобальным тумблером в нижней статус-строке и сохраняется между сессиями через `schema_meta`.

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
- `CreateBudget.execute(category, start_date, end_date, limit_kzt, include_mandatory=False)` — создание бюджета.
- `DeleteBudget.execute(budget_id)` — удаление бюджета.
- `UpdateBudgetLimit.execute(budget_id, new_limit_kzt)` — обновление лимита бюджета.
- `GetBudgets.execute()` — список бюджетов.
- `GetBudgetResults.execute()` — список live-результатов по бюджетам.

`app/use_case_support.py`

- Общие helper'ы для сценариев use case без собственной доменной логики.

`app/finance_service.py`

- Протокол `FinanceService` для import-оркестратора (`ImportService`).
- Явно описывает методы импорта, rollback и нормализации идентификаторов.

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
- `execute(...)` / `commit()` — низкоуровневые операции, используемые budget- и audit-сервисами.
- При записи поддерживает dual storage для денег: `REAL` + `*_minor`, а для курсов — `REAL` + `rate_at_operation_text`.

`storage/base.py`

- `Storage` — минимальный контракт хранения (`get/save` для wallets/records/transfers и `get` для mandatory expenses).

`storage/json_storage.py`

- `JsonStorage(file_path="data.json")` — JSON-обёртка только для import/export/backup сценариев.

`storage/sqlite_storage.py`

- `SQLiteStorage(db_path="records.db")` — SQLite-адаптер на `sqlite3`, включает:
  - `PRAGMA foreign_keys = ON`;
  - `PRAGMA journal_mode = WAL`;
  - auto-migration существующих БД: добавляет `*_minor` и `rate_at_operation_text`, затем backfill'ит их;
  - чтение/запись доменных объектов без дублирования бизнес-логики.

`db/schema.sql`

- SQL-схема БД: таблицы `wallets`, `records`, `transfers`, `mandatory_expenses`, `budgets`, `debts`, `debt_payments`, ограничения и индексы.
- Для денежных полей предусмотрены точные integer-колонки `*_minor`; для курсов — `rate_at_operation_text`.
- Для бюджетов предусмотрены `limit_kzt_minor`, флаг `include_mandatory` и индексы по категории/датам.
- Для debt-flow предусмотрены `records.related_debt_id`, таблицы `debts` / `debt_payments` и индексы по `status`, `contact_name`, `debt_id`, `record_id`.

### GUI

`gui/tkinter_gui.py`

- `FinancialApp` — основной класс приложения с Tkinter.
- Приложение открывает окно на базе `bootstrap_repository(run_maintenance=False)`, затем выполняет deferred startup maintenance и lazy tab build.

`gui/tabs/infographics_tab.py`

- `InfographicsTabBindings` — класс для привязки событий к элементам интерфейса вкладки `Infographics`.
- `build_infographics_tab(parent, on_chart_filter_change, on_refresh_charts, on_legend_mousewheel, bind_all, after, after_cancel)` — метод для построения интерфейса вкладки `Infographics`. Эта вкладка отображает диаграммы и сводки по финансовым данным.

`gui/tabs/operations_tab.py`

- `OperationsTabContext` — контекст вкладки операций.
- `OperationsTabBindings` — класс для привязки событий к элементам интерфейса вкладки `Operations`.
- `show_import_preview_dialog(parent, filepath, policy_label, preview, force=False)` — модальный preview-диалог dry-run импорта.
- `build_operations_tab(parent, context, import_formats)` — метод для построения интерфейса вкладки `Operations`. Эта вкладка поддерживает добавление и удаление записей, редактирование валютных значений, создание переводов, category `Combobox` с подсказками, общий refresh list/charts/wallets/budgets и двухшаговый import flow `dry-run -> preview -> commit`.

`gui/tabs/budget_tab.py`

- `BudgetTabBindings` — привязки виджетов вкладки `Budget`.
- `build_budget_tab(parent, context)` — построение вкладки `Budget` с формой создания, таблицей бюджетов, progress canvas и callback `refresh`.

`gui/tabs/debts_tab.py`

- `DebtsTabBindings` — привязки виджетов вкладки `Debts`.
- `build_debts_tab(parent, context)` — построение вкладки `Debts` с формой создания, таблицей долгов, history-блоком и progress canvas.
- `refresh_debts_views(context)` — единый refresh list/charts/wallets/all после debt-операций.

`gui/tabs/distribution_tab.py`

- `DistributionTabBindings` — привязки виджетов вкладки `Distribution`.
- `build_distribution_tab(parent, context)` — построение вкладки `Distribution` со structure editor, period range и таблицей фиксированных/live распределений.

`gui/tabs/reports_tab.py`

- `ReportsTabContext` — контекст вкладки отчетов.
- `build_reports_tab(parent, context)` — построение вкладки `Reports`:
  - фильтры `Period` / `Period end` / `Category` / `Wallet`;
  - `Group by category` с drill‑down (double-click) и кнопкой `Back`;
  - `Totals mode`: `On fixed rate` / `On current rate` (обновляет блок `Summary`);
  - экспорт через меню `Export` (`CSV`/`XLSX`/`PDF`).

`gui/tabs/reports_controller.py`

- `ReportsController` — адаптер между `FinancialController` и UI отчётов (валидация фильтров, сбор summary/операций/месячных строк).
- Для wallet-filter summary использует баланс выбранного кошелька, а не глобальный net worth.

`gui/record_colors.py`

- `KIND_TO_FOREGROUND` / `foreground_for_kind(kind)` — палитра и выбор цвета для типов записей (`income`/`expense`/`mandatory`/`transfer`).

`gui/tooltip.py`

- `Tooltip(widget, text)` — простой tooltip для `tkinter`/`ttk` виджетов.
- Позиционирование tooltip учитывает границы окна приложения и корректно работает в multi-monitor конфигурациях.

`gui/controller_import_support.py`

- Helper'ы для импорт-транзакций GUI-контроллера: `run_import_transaction(...)`, `normalize_operation_ids_for_import(...)`.

`gui/tabs/operations_support.py`

- Общие helper'ы вкладки `Operations`: preview-диалог импорта, безопасное destroy и единый refresh операций/графиков/кошельков/бюджетов.

`gui/tabs/settings_support.py`

- Общие helper'ы вкладки `Settings`: audit dialog и безопасное закрытие временных окон.

`gui/tabs/analytics_tab.py`

- `AnalyticsTabBindings` — привязки виджетов для вкладки `Analytics`.
- `build_analytics_tab(parent, context)` — построение вкладки `Analytics` (Dashboard, Category Breakdown, Monthly Report, Net Worth Timeline).
- Dashboard включает tooltip с пояснениями метрик и отображает `Year expense` вместо annualized expense.

`gui/tabs/settings_tab.py`

- `SettingsTabContext` — контекст вкладки настроек.
- `build_settings_tab(parent, context, import_formats)` — метод для построения интерфейса вкладки `Settings`. Эта вкладка позволяет управлять кошельками, обязательными расходами, backup и запуском аудита.
- `show_audit_report_dialog(report, parent)` — модальный диалог результата аудита с секциями `Errors`, `Warnings`, `Passed`.
- Изменения кошельков и обязательных расходов синхронно обновляют и вкладку бюджетов.

`gui/controllers.py`

- `FinancialController` — класс управления бизнес-логикой приложения.
- `get_income_categories()` — список существующих категорий доходов для `Combobox`.
- `get_expense_categories()` — список существующих категорий расходов для `Combobox`.
- `get_mandatory_expense_categories()` — список существующих категорий обязательных расходов для `Combobox`.
- `import_records(fmt, filepath, policy, force=False, dry_run=False)` — единая точка входа для dry-run и реального импорта операций.
- `import_mandatory(fmt, filepath)` — импорт шаблонов обязательных расходов с результатом `ImportResult`.
- `run_audit()` — запуск Data Audit Engine через use case и возврат `AuditReport`.
- `get_net_worth_timeline()` — net worth (KZT) на конец каждого месяца (Timeline Engine, только SQLite).
- `get_monthly_cashflow(start_date=None, end_date=None)` — доходы/расходы/cashflow по месяцам (исключая переводы).
- `get_cumulative_income_expense()` — накопительные суммы доходов и расходов по месяцам (исключая переводы).
- `get_savings_rate(start_date, end_date)` — норма сбережений (%) за период (Metrics Engine, только SQLite).
- `get_burn_rate(start_date, end_date)` — средний дневной расход (KZT) (Metrics Engine, только SQLite).
- `get_year_income(year, up_to_date=None)` — доходы за календарный год, опционально year-to-date.
- `get_year_expense(year, up_to_date=None)` — расходы за календарный год, опционально year-to-date.
- `get_spending_by_category(start_date, end_date, limit=None)` — расходы по категориям (Metrics Engine, только SQLite).
- `get_income_by_category(start_date, end_date, limit=None)` — доходы по категориям (Metrics Engine, только SQLite).
- `get_top_expense_categories(start_date, end_date, top_n=5)` — топ категорий расходов (Metrics Engine, только SQLite).
- `get_monthly_summary(start_date=None, end_date=None)` — месячные агрегаты (Metrics Engine, только SQLite).
- `get_average_monthly_income(start_date, end_date)` — средний месячный доход по диапазону.
- `get_average_monthly_expenses(start_date, end_date)` — среднемесячные расходы по диапазону.
- `create_budget(...)`, `get_budgets()`, `get_budget_results()`, `delete_budget(...)`,  `update_budget_limit(...)`, `replace_budgets(...)` — API Budget System.
- `create_debt(...)`, `create_loan(...)`, `get_debts(wallet_id=None)`, `get_open_debts()`, `get_closed_debts()`, `get_debt_history(debt_id)` — API Debt System.
- `register_debt_payment(...)`, `register_debt_write_off(...)`, `close_debt(...)`, `delete_debt(...)`, `delete_debt_payment(...)`, `recalculate_debt(...)` — lifecycle debt/loan операций.
- `create_distribution_item(...)`, `create_distribution_subitem(...)`, `update_distribution_item_pct(...)`, `update_distribution_subitem_pct(...)`, `delete_distribution_item(...)`, `delete_distribution_subitem(...)` — CRUD API Distribution System.
- `validate_distribution()`, `get_distribution_history(start_month, end_month)`, `get_frozen_distribution_rows(...)`, `toggle_distribution_month_fixed(month)` — расчёт и управление frozen distribution rows.

`gui/exporters.py`

- `export_report(report, filepath, fmt, debts=None)` — экспорт отчёта; `XLSX`/`PDF` могут включать debt summary секции.
- `export_grouped_report(statement_title, grouped_rows, filepath, fmt)` — экспорт grouped summary отчёта.
- `export_mandatory_expenses(expenses, filepath, fmt)`.
- `export_records(records, filepath, fmt, initial_balance=0.0, transfers=None)`.
- `export_full_backup(filepath, wallets, records, mandatory_expenses, budgets=(), debts=(), debt_payments=(), distribution_items=(), distribution_subitems=(), distribution_snapshots=(), transfers=None, initial_balance=0.0, readonly=True, storage_mode="unknown")`.

`gui/importers.py`

- Legacy-обёртки над `utils/*` для обратной совместимости и unit-тестов.
- Для реальных import flows приложения предпочтителен `FinancialController.import_records(...)` / `ImportService.import_file(...)`.

`gui/helpers.py`

- `open_in_file_manager(path)`.

`gui/controller_support.py`

- Вспомогательные структуры и helper'ы для GUI-контроллера (`RecordListItem`, list-building, import normalization).

### Services

`services/import_parser.py`

- `parse_import_file(path, force=False)` -> `ParsedImportData` (DTO/словарный слой, без записи в хранилище).
- Валидация ограничений: размер файла, row-limit, размер CSV-поля.
- Для `JSON` также читает `budgets`, `debts`, `debt_payments`, `distribution_items`, `distribution_subitems` и `distribution_snapshots`.
- `parse_transfer_row(...)` поддерживает legacy transfer-строки и current-rate/full-backup сценарии через единый parser.

`services/import_service.py`

- `ImportService.import_file(path, force=False, dry_run=False)` — dry-run или реальный импорт операций; возвращает `ImportResult`.
- `ImportService.import_mandatory_file(path)` — импорт шаблонов обязательных расходов; возвращает `ImportResult`.
- Это основной app-level API для импорта через GUI/controller.
- Dry-run использует тот же parse/validation pipeline, но не пишет в SQLite.
- `Full Backup` сохраняет фиксированные `amount_kzt/rate_at_operation`; `Current Rate` пересчитывает значения.
- Для `JSON` full backup может восстанавливать budgets, debts, debt_payments, структуру распределения и frozen distribution snapshots через основной import pipeline `replace_all_data(...)` и distribution/budget hooks.
- Для `JSON` full backup битая структура распределения теперь считается ошибкой импорта, а не silently-skipped данными.

`services/audit_service.py`

- `AuditService(repository)` — read-only сервис диагностики SQLite.
- `run()` — сканирует SQLite и выполняет 11 проверок целостности и консистентности.
- Все проверки возвращают `AuditFinding`, а при отсутствии нарушений формируют один `OK` finding на check.

`services/report_service.py`

- DTO-модели и helper'ы для UI отчётов: `ReportFilters`, `ReportSummary`, `ReportsResult`,
  `build_operations_rows(report)`, `build_monthly_rows(report)`, `extract_categories(rows)`.
- Debt summary для `XLSX`/`PDF` формируется отдельно и фильтруется по периоду/кошельку через `utils/debt_report_utils.py`.

`services/balance_service.py`

- `WalletBalance(wallet_id, name, currency, balance)` — immutable snapshot баланса кошелька.
- `CashflowResult(income, expenses, cashflow)` — immutable агрегат по периоду.
- `BalanceService(repository, currency_service=None)` — read-only аналитика по `wallets` + `records`.
- При передаче `currency_service` начальные балансы кошельков нормализуются в KZT до агрегации.
- SQL-агрегации опираются на `*_minor`, когда они доступны, чтобы избежать накопления float-ошибок.
- `get_wallet_balance(wallet_id, date=None)` — баланс кошелька на дату или по полной истории.
- `get_wallet_balances(date=None)` — список балансов всех активных кошельков.
- `get_total_balance(date=None)` — суммарный баланс системы с учётом открытых debts/loans.
- `get_cashflow(start_date, end_date)` — доходы, расходы и net cashflow без double-counting transfer.
- `get_income(start_date, end_date)` — доходы за период без transfer.
- `get_expenses(start_date, end_date)` — расходы за период, включая `mandatory_expense`.

`services/timeline_service.py`

- `MonthlyNetWorth(month, balance)` — immutable snapshot net worth на конец месяца.
- `MonthlyCashflow(month, income, expenses, cashflow)` — immutable агрегат cashflow по месяцу.
- `MonthlyCumulative(month, cumulative_income, cumulative_expenses)` — immutable накопительные суммы по месяцам.
- `TimelineService(repository, currency_service=None)` — read-only аналитика по timeline из `wallets` + `records`.
- При передаче `currency_service` timeline корректно учитывает multi-currency `wallet.initial_balance`.
- Для денежных сумм использует SQL helper-выражения над `*_minor`.
- `get_net_worth_timeline()` — net worth (KZT) на конец каждого месяца (включая transfer-пары, они нейтральны).
- `get_monthly_cashflow(start_date=None, end_date=None)` — доходы/расходы/cashflow по месяцам (исключая `transfer_id IS NOT NULL`).
- `get_cumulative_income_expense()` — накопительные доходы и расходы по месяцам (исключая `transfer_id IS NOT NULL`).

`services/metrics_service.py`

- `CategorySpend(category, total_kzt, record_count)` — immutable агрегат по категории.
- `MonthlySummary(month, income, expenses, cashflow, savings_rate)` — immutable агрегат по месяцу.
- `MetricsService(repository)` — read-only аналитика финансовых метрик по `records`.
- Для сумм и сравнений использует quantized money / minor-unit SQL.
- `get_savings_rate(start_date, end_date)` — (income - expenses) / income * 100, safe division by zero.
- `get_burn_rate(start_date, end_date)` — average daily expenses (KZT) for date range.
- `get_spending_by_category(start_date, end_date, limit=None)` — расходы по категориям, сортировка по убыванию.
- `get_income_by_category(start_date, end_date, limit=None)` — доходы по категориям, сортировка по убыванию.
- `get_distinct_income_categories()` — уникальные категории доходов.
- `get_distinct_expense_categories()` — уникальные категории расходов.
- `get_distinct_mandatory_expense_categories()` — уникальные категории обязательных расходов.
- `get_top_expense_categories(start_date, end_date, top_n=5)` — wrapper над `get_spending_by_category`.
- `get_monthly_summary(start_date=None, end_date=None)` — агрегаты по месяцам (income/expenses/cashflow/savings_rate).

`services/budget_service.py`

- `BudgetService(repository)` — сервис управления бюджетами и live spend-tracking.
- `create_budget(category, start_date, end_date, limit_kzt, include_mandatory)` — создание нового бюджета.
- `get_budgets()` — список всех бюджетов.
- `delete_budget(budget_id)` — удаление бюджета.
- `update_budget_limit(budget_id, new_limit_kzt)` — обновление лимита бюджета.
- `replace_budgets(budgets)` — полная замена budget-данных при JSON full-backup import.
- `get_budget_result(budget, today)` — результаты по бюджету на указанную дату.
- `get_all_results(today)` — batch-расчёт всех результатов по бюджетам на указанную дату.

`services/debt_service.py`

- `DebtService(repository)` — сервис жизненного цикла долгов и ссуд поверх SQLite.
- `create_debt(...)` / `create_loan(...)` — создание обязательства и связанного стартового cashflow record.
- `register_payment(...)` / `register_write_off(...)` — погашение через wallet-linked record или списание без движения кошелька.
- `close_debt(...)`, `delete_debt(...)`, `delete_payment(...)`, `recalculate_debt(...)` — закрытие, удаление и восстановление консистентного остатка.
- `get_all_debts()`, `get_open_debts()`, `get_closed_debts()`, `get_debt_history(debt_id)` — выборки и история.

`services/distribution_service.py`

- `DistributionService(repository)` — CRUD структуры распределения и расчёт monthly distribution только для SQLite.
- `create_item(...)`, `create_subitem(...)`, `update_*_pct(...)`, `update_*_name(...)`, `delete_*(...)` — управление item/subitem структурой.
- `validate()` — проверка, что top-level и subitem percentages сходятся к `100%`.
- `get_monthly_distribution(month)` / `get_distribution_history(start_month, end_month)` — расчёт распределения по net income без переводов.
- `freeze_month(month, auto_fixed=False)`, `freeze_closed_months()`, `toggle_month_fixed(month)`, `get_frozen_rows(...)`, `replace_frozen_rows(rows)` — lifecycle frozen snapshot'ов.

`services/currency_support.py`

- `convert_money_to_kzt(amount, currency, currency_service=None)` — helper нормализации сумм в KZT для read-only сервисов и use cases.

`services/sqlite_money_sql.py`

- SQL helper-выражения для minor-unit сумм: `minor_amount_expr`, `money_expr`, `signed_minor_amount_expr`.

### Utils

`utils/backup_utils.py`

- `compute_checksum(data)` — SHA256 для `data`.
- `export_full_backup_to_json(filepath, wallets, records, mandatory_expenses, budgets=(), debts=(), debt_payments=(), distribution_items=(), distribution_subitems=(), distribution_snapshots=(), transfers=(), initial_balance=0.0, readonly=True, storage_mode="unknown")`.
- `import_full_backup_from_json(filepath, force=False)` — legacy-compatible helper для backup JSON parsing; читает также `debts` / `debt_payments`, но для реального импорта приложения предпочтителен `ImportService.import_file(...)`.
- Backup/import нормализует денежные значения и курсы через `utils.money`.
- JSON export writes atomically via temporary file + `os.replace`.

`utils/debt_report_utils.py`

- `debts_for_report_period(report, debts)` — отбирает долги/ссуды, пересекающиеся с периодом отчёта.
- `debt_progress_percent(debt)` — вычисляет процент закрытия обязательства для export-summary.

`utils/money.py`

- Общие helper'ы точной денежной арифметики: `quantize_money`, `quantize_rate`, `to_minor_units`, `minor_to_money`, `build_rate`, diff/helper-функции.

`utils/csv_utils.py`

- `report_to_csv(report, filepath)`.
- `report_from_csv(filepath)`.
- `export_records_to_csv(records, filepath, initial_balance=0.0, transfers=None)`.
- `import_records_from_csv(filepath, policy, currency_service, wallet_ids=None)`.
- `export_mandatory_expenses_to_csv(expenses, filepath)`.
- `import_mandatory_expenses_from_csv(filepath, policy, currency_service)`.
- CSV import/export валидирует и квантует суммы/курсы без float-drift; integrity checks transfer используют quantized comparison.

`utils/excel_utils.py`

- `report_to_xlsx(report, filepath)`.
- `report_from_xlsx(filepath)`.
- `export_records_to_xlsx(records, filepath, initial_balance=0.0, transfers=None)`.
- `import_records_from_xlsx(filepath, policy, currency_service, wallet_ids=None)`.
- `export_mandatory_expenses_to_xlsx(expenses, filepath)`.
- `import_mandatory_expenses_from_xlsx(filepath, policy, currency_service)`.
- `existing_initial_balance` при импорте quantize'ится до money scale.
- XLSX export добавляет стили заголовков/секций/итогов, `freeze_panes`, `auto_filter`, auto-width и сохраняет числовые суммы как numeric cells.

`utils/tabular_utils.py`

- Общие helper'ы для CSV/XLSX row-building, type label formatting и rate resolver.

`utils/pdf_utils.py`

- `report_to_pdf(report, filepath)`.

`utils/charting.py`

- `aggregate_expenses_by_category(records)`.
- `aggregate_daily_cashflow(records, year, month)`.
- `aggregate_monthly_cashflow(records, year)`.
- `extract_years(records)`.

`utils/import_core.py`

- Базовый parser import-строк с Decimal-based money parsing, quantization и валидацией payload.
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
├── main.py                           # Точка входа приложения
├── config.py                         # Пути runtime SQLite и JSON import/export
├── bootstrap.py                      # Инициализация SQLite + стартовая валидация
├── backup.py                         # Backup JSON и экспорт SQLite -> JSON
├── migrate_json_to_sqlite.py         # Миграция данных из JSON в SQLite
├── version.py                        # Версия приложения для snapshot metadata
├── data.json                         # JSON import/export/backup файл (опционально)
├── currency_rates.json               # Кэш курсов валют для online-режима
├── requirements.txt                  # Runtime-зависимости
├── requirements-dev.txt              # Dev-зависимости (тесты, coverage)
├── pytest.ini                        # Настройки pytest
├── pyproject.toml                    # Конфигурация проекта
├── README.md                         # Эта документация
├── README_EN.md                      # Документация на английском
├── CHANGELOG.md                      # История изменений
├── LICENSE                           # Лицензия
│
├── app/                              # Application layer
│   ├── __init__.py
│   ├── finance_service.py            # Протокол FinanceService для import-сервиса
│   ├── record_service.py             # Сервис записей
│   ├── services.py                   # CurrencyService адаптер
│   ├── use_case_support.py           # Общие helper'ы для use cases
│   └── use_cases.py                  # Сценарии использования
│
├── domain/                           # Domain layer
│   ├── __init__.py
│   ├── audit.py                      # Модели и логика аудита
│   ├── budget.py                     # Бюджеты, pace/status и live tracking DTO
│   ├── debt.py                       # Долги, ссуды и debt-payment модели
│   ├── distribution.py               # DTO и frozen snapshot-модели Distribution System
│   ├── records.py                    # Записи
│   ├── reports.py                    # Отчёты
│   ├── currency.py                   # Доменный CurrencyService
│   ├── wallets.py                    # Кошельки
│   ├── transfers.py                  # Переводы
│   ├── validation.py                 # Валидация дат и периодов
│   ├── errors.py                     # Ошибки приложения
│   ├── import_policy.py              # Политики импорта
│   └── import_result.py              # Результаты импорта
│
├── infrastructure/                   # Infrastructure layer
│   ├── repositories.py               # JSON-репозиторий
│   └── sqlite_repository.py          # SQLite-репозиторий
│
├── storage/                          # Абстракция storage и адаптеры JSON/SQLite
│   ├── __init__.py
│   ├── base.py                       # Базовый класс хранилища
│   ├── json_storage.py               # Адаптер JSON-хранилища
│   └── sqlite_storage.py             # Адаптер SQLite-хранилища
│
├── db/                               # SQL schema для SQLite
│   └── schema.sql
│
├── services/                         # Сервисный слой
│   ├── __init__.py
│   ├── audit_service.py              # Сервис аудита
│   ├── balance_service.py            # Read-only сервис балансов и cashflow
│   ├── budget_service.py             # CRUD бюджетов и live spend-tracking
│   ├── currency_support.py           # Конвертация денежных сумм в KZT для сервисов
│   ├── debt_service.py               # Debt/Loan lifecycle service
│   ├── distribution_service.py       # CRUD структуры распределения и frozen month snapshots
│   ├── import_parser.py              # Парсер CSV/XLSX/JSON -> DTO
│   ├── import_service.py             # Оркестрация импорта через FinanceService
│   ├── metrics_service.py            # Read-only сервис финансовых метрик
│   ├── report_service.py             # DTO и helper'ы для UI отчётов
│   ├── sqlite_money_sql.py           # SQL helper-выражения для minor-unit сумм
│   └── timeline_service.py           # Read-only сервис временных рядов
│
├── utils/                            # Импорт/экспорт и графики
│   ├── __init__.py
│   ├── backup_utils.py               # Резервное копирование данных
│   ├── debt_report_utils.py          # Debt summary helpers для report export
│   ├── import_core.py                # Валидатор импорта
│   ├── charting.py                   # Графики и агрегации
│   ├── csv_utils.py
│   ├── excel_utils.py
│   ├── money.py                      # Точная денежная арифметика и quantization helper'ы
│   ├── pdf_utils.py
│   └── tabular_utils.py              # Общие helper'ы CSV/XLSX
│
├── gui/                              # GUI слой (Tkinter)
│   ├── tabs/
│   │   ├── infographics_tab.py       # Вкладка с информационными графиками
│   │   ├── operations_tab.py         # Вкладка с операциями и переводами
│   │   ├── operations_support.py     # Общие helper'ы вкладки операций
│   │   ├── reports_tab.py            # Вкладка с отчётами
│   │   ├── reports_controller.py     # Контроллер вкладки отчётов (UI adapter)
│   │   ├── analytics_tab.py          # Вкладка аналитики (dashboard, категории, отчёт)
│   │   ├── budget_tab.py             # Вкладка бюджетов и progress canvas
│   │   ├── debts_tab.py              # Вкладка долгов и ссуд
│   │   ├── distribution_tab.py       # Вкладка распределения net income по месяцам
│   │   ├── settings_support.py       # Общие helper'ы вкладки настроек
│   │   └── settings_tab.py           # Вкладка с кошельками и обязательными расходами
│   │
│   ├── __init__.py
│   ├── tkinter_gui.py                # Основное GUI-приложение
│   ├── record_colors.py              # Цвета строк по типу записи
│   ├── tooltip.py                    # Tooltip для tkinter/ttk
│   ├── controller_import_support.py  # Helper'ы import flow для GUI-контроллера
│   ├── controller_support.py         # Вспомогательные GUI helper'ы
│   ├── helpers.py                    # Помощники для GUI
│   ├── controllers.py                # Контроллеры GUI
│   ├── importers.py                  # Legacy-обёртки импортеров (совместимость/тесты)
│   └── exporters.py                  # Экспорт отчётов, записей, обязательных расходов и backup
│
└── tests/                            # Тесты
    ├── __init__.py
    ├── conftest.py                   # Локальная tmp-fixture для стабильных тестов
    ├── test_analytics_tab.py
    ├── test_audit_engine.py
    ├── test_balance_service.py
    ├── test_bootstrap_backup.py
    ├── test_bootstrap_migration_verification.py
    ├── test_budget_service.py
    ├── test_charting.py
    ├── test_csv.py
    ├── test_currency.py
    ├── test_debt_controller.py
    ├── test_debt_domain.py
    ├── test_debt_service.py
    ├── test_debts_tab.py
    ├── test_distribution_service.py
    ├── test_excel.py
    ├── test_gui_exporters_importers.py
    ├── test_import_balance_contract.py
    ├── test_import_core.py
    ├── test_import_dry_run.py
    ├── test_import_parser.py
    ├── test_import_policy_and_backup.py
    ├── test_import_security.py
    ├── test_import_service.py
    ├── test_mandatory_ux.py
    ├── test_metrics_service.py
    ├── test_migrate_json_to_sqlite.py
    ├── test_online_mode.py
    ├── test_pdf.py
    ├── test_records.py
    ├── test_reports.py
    ├── test_reports_controller.py
    ├── test_repositories.py
    ├── test_schema_contracts.py
    ├── test_services.py
    ├── test_sqlite_runtime_storage.py
    ├── test_tooltip.py
    ├── test_timeline_service.py
    ├── test_transfer_integrity.py
    ├── test_transfer_order_sqlite.py
    ├── test_use_cases.py
    ├── test_validation.py
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

По умолчанию приложение использует локальные курсы. Online-режим можно включить как при создании `CurrencyService(use_online=True)`, так и позже через `CurrencyService.set_online(True)` или тумблер `Online` в нижней статус-строке. При успешной загрузке курсы НБ РК сохраняются в `currency_rates.json`, а статус-строка показывает время последнего обновления.

---

## 📄 Лицензия

MIT License — свободное использование, модификация и распространение.
