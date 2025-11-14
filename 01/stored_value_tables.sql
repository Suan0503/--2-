-- 儲值金相關資料表 DDL (SQLite / PostgreSQL 通用簡化版)
-- Wallet: 每個手機/白名單使用者一個錢包
CREATE TABLE IF NOT EXISTS stored_value_wallet (
  id SERIAL PRIMARY KEY,
  whitelist_id INTEGER,
  phone VARCHAR(20),
  balance INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_coupon_notice_at TIMESTAMP NULL
);
CREATE INDEX IF NOT EXISTS idx_wallet_phone ON stored_value_wallet(phone);
CREATE INDEX IF NOT EXISTS idx_wallet_whitelist_id ON stored_value_wallet(whitelist_id);

-- Transaction: 每筆儲值或扣款記錄
CREATE TABLE IF NOT EXISTS stored_value_txn (
  id SERIAL PRIMARY KEY,
  wallet_id INTEGER NOT NULL,
  type VARCHAR(20) NOT NULL, -- topup / consume
  amount INTEGER NOT NULL,
  remark TEXT,
  coupon_500_count INTEGER NOT NULL DEFAULT 0,
  coupon_300_count INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_txn_wallet_id ON stored_value_txn(wallet_id);

-- 折價券統計檢視 (可選，如不支援 VIEW 可在程式運算)
-- CREATE VIEW wallet_coupon_summary AS
-- SELECT wallet_id,
--   COALESCE(SUM(CASE WHEN type='topup' THEN coupon_500_count ELSE -coupon_500_count END),0) AS coupon500_remaining,
--   COALESCE(SUM(CASE WHEN type='topup' THEN coupon_300_count ELSE -coupon_300_count END),0) AS coupon300_remaining
-- FROM stored_value_txn
-- GROUP BY wallet_id;
