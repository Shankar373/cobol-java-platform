-- DB2GROUPBY01 per-repo seed: GROUP BY DEPT_ID HAVING COUNT(*) > 1 needs dept 10 with 2+ rows
-- Idempotent: ON CONFLICT DO NOTHING so re-runs are safe.
INSERT INTO customer (cust_id, cust_name, dept_id) VALUES (101, 'TEST C1', 10) ON CONFLICT (cust_id) DO NOTHING;
INSERT INTO customer (cust_id, cust_name, dept_id) VALUES (102, 'TEST C2', 10) ON CONFLICT (cust_id) DO NOTHING;
INSERT INTO customer (cust_id, cust_name, dept_id) VALUES (103, 'TEST C3', 20) ON CONFLICT (cust_id) DO NOTHING;
