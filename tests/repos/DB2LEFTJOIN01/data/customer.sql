-- DB2LEFTJOIN01 per-repo seed: LEFT JOIN test requires CUSTOMER(101, dept_id=NULL)
-- dept_id=NULL → WS-DEPT-IND=-1 → program displays "DEPT: NULL"
-- Idempotent: ON CONFLICT DO NOTHING so re-runs are safe.
INSERT INTO customer (cust_id, cust_name, dept_id) VALUES (101, 'TEST CUSTOMER', NULL) ON CONFLICT (cust_id) DO NOTHING;
