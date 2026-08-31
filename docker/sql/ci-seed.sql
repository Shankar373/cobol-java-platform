-- ci-seed.sql: Idempotent schema + seed data for all DB2 test repos.
-- Run once after PostgreSQL starts. Safe to re-run (IF NOT EXISTS + ON CONFLICT).
-- Database: modernization_db  User: modernize

-- ─── customer ────────────────────────────────────────────────────────────────
-- STATUS column required by DB2AGGREGATE01 (SELECT COUNT(*) WHERE STATUS=?)
CREATE TABLE IF NOT EXISTS customer (
    cust_id   INT PRIMARY KEY,
    cust_name VARCHAR(100),
    dept_id   INT,
    status    VARCHAR(10) DEFAULT 'ACTIVE'
);

-- ─── orders ──────────────────────────────────────────────────────────────────
-- AMOUNT column required by DB2SUBQUERY01 (WHERE AMOUNT > :WS-AMT)
CREATE TABLE IF NOT EXISTS orders (
    order_id    INT PRIMARY KEY,
    customer_id INT,
    order_date  DATE,
    amount      DECIMAL(10,2) DEFAULT 0
);

-- ─── dept ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dept (
    dept_id   INT PRIMARY KEY,
    dept_name VARCHAR(100)
);

-- ─── db2_test_e2e (DB2E2E01) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS db2_test_e2e (
    id   INT PRIMARY KEY,
    name VARCHAR(20)
);

-- ─── Seed data ───────────────────────────────────────────────────────────────
-- dept must be seeded before customer (no FK but keeps data consistent).
INSERT INTO dept (dept_id, dept_name) VALUES (10, 'ENGINEERING') ON CONFLICT (dept_id) DO NOTHING;

-- Two ACTIVE customers with dept_id=10 → satisfies:
--   DB2AGGREGATE01: COUNT(*) WHERE STATUS='ACTIVE' = 2
--   DB2GROUPBY01:   GROUP BY DEPT_ID HAVING COUNT(*) > 1 → dept 10 with 2 rows
-- Customer 101: dept_id=NULL → DB2LEFTJOIN01 LEFT JOIN → WS-DEPT-IND=-1 → "DEPT: NULL"
INSERT INTO customer (cust_id, cust_name, dept_id, status)
    VALUES (101, 'TEST CUSTOMER', NULL, 'ACTIVE')    ON CONFLICT (cust_id) DO NOTHING;
INSERT INTO customer (cust_id, cust_name, dept_id, status)
    VALUES (102, 'ANOTHER CUST', 10, 'ACTIVE')       ON CONFLICT (cust_id) DO NOTHING;
INSERT INTO customer (cust_id, cust_name, dept_id, status)
    VALUES (103, 'NULL TEST CUST', 10, 'INACTIVE')   ON CONFLICT (cust_id) DO NOTHING;

-- orders: customer_id=101 with amount=1000 → satisfies:
--   DB2JOIN01:      INNER JOIN customer WHERE cust_id=101 → "CUST: TEST CUSTOMER / ORDER: 2024-01-15"
--   DB2SUBQUERY01:  WHERE cust_id IN (SELECT customer_id FROM orders WHERE amount > 500) → finds 101
INSERT INTO orders (order_id, customer_id, order_date, amount)
    VALUES (1, 101, '2024-01-15', 1000.00) ON CONFLICT (order_id) DO NOTHING;

INSERT INTO db2_test_e2e (id, name) VALUES (1, 'INIT') ON CONFLICT (id) DO NOTHING;
