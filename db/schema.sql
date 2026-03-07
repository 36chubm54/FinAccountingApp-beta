PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK(length(trim(name)) > 0),
    currency TEXT NOT NULL CHECK(length(trim(currency)) >= 3),
    initial_balance REAL NOT NULL DEFAULT 0 CHECK(initial_balance >= 0),
    system INTEGER NOT NULL DEFAULT 0 CHECK(system IN (0, 1)),
    allow_negative INTEGER NOT NULL DEFAULT 0 CHECK(allow_negative IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_wallet_id INTEGER NOT NULL,
    to_wallet_id INTEGER NOT NULL,
    date TEXT NOT NULL CHECK(length(date) = 10),
    amount_original REAL NOT NULL CHECK(amount_original > 0),
    currency TEXT NOT NULL CHECK(length(trim(currency)) >= 3),
    rate_at_operation REAL NOT NULL CHECK(rate_at_operation > 0),
    amount_kzt REAL NOT NULL CHECK(amount_kzt > 0),
    description TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(from_wallet_id) REFERENCES wallets(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY(to_wallet_id) REFERENCES wallets(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    CHECK(from_wallet_id <> to_wallet_id)
);

CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('income', 'expense', 'mandatory_expense')),
    date TEXT NOT NULL CHECK(length(date) = 10),
    wallet_id INTEGER NOT NULL,
    transfer_id INTEGER,
    amount_original REAL NOT NULL CHECK(amount_original >= 0),
    currency TEXT NOT NULL CHECK(length(trim(currency)) >= 3),
    rate_at_operation REAL NOT NULL CHECK(rate_at_operation > 0),
    amount_kzt REAL NOT NULL CHECK(amount_kzt >= 0),
    category TEXT NOT NULL CHECK(length(trim(category)) > 0),
    description TEXT NOT NULL DEFAULT '',
    period TEXT CHECK(period IN ('daily', 'weekly', 'monthly', 'yearly') OR period IS NULL),
    FOREIGN KEY(wallet_id) REFERENCES wallets(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY(transfer_id) REFERENCES transfers(id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mandatory_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER NOT NULL,
    amount_original REAL NOT NULL CHECK(amount_original >= 0),
    currency TEXT NOT NULL CHECK(length(trim(currency)) >= 3),
    rate_at_operation REAL NOT NULL CHECK(rate_at_operation > 0),
    amount_kzt REAL NOT NULL CHECK(amount_kzt >= 0),
    category TEXT NOT NULL CHECK(length(trim(category)) > 0),
    description TEXT NOT NULL CHECK(length(trim(description)) > 0),
    period TEXT NOT NULL CHECK(period IN ('daily', 'weekly', 'monthly', 'yearly')),
    FOREIGN KEY(wallet_id) REFERENCES wallets(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_records_date ON records(date);
CREATE INDEX IF NOT EXISTS idx_records_wallet_id ON records(wallet_id);
CREATE INDEX IF NOT EXISTS idx_transfers_date ON transfers(date);
CREATE INDEX IF NOT EXISTS idx_transfers_wallet_from ON transfers(from_wallet_id);
CREATE INDEX IF NOT EXISTS idx_transfers_wallet_to ON transfers(to_wallet_id);
CREATE INDEX IF NOT EXISTS idx_mandatory_expenses_wallet_id ON mandatory_expenses(wallet_id);
