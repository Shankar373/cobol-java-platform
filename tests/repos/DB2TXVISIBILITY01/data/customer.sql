-- Ensure the customer table exists with the full column set used across repos.
-- A non-empty seed is required so the generated program runs its TRUNCATE step:
-- with an empty data file, seed_queries is empty and the TRUNCATE block is
-- skipped, so rows left over from other shared-table tests persist and cause
-- primary-key conflicts / stale reads that break commit & rollback visibility.
CREATE TABLE IF NOT EXISTS customer (cust_id INT PRIMARY KEY, cust_name VARCHAR(100), dept_id INT, status VARCHAR(20));
