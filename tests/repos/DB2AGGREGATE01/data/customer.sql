-- DB2AGGREGATE01 per-repo seed: COUNT(*) WHERE STATUS='ACTIVE' test needs 2 ACTIVE rows
-- Idempotent: ON CONFLICT DO NOTHING so re-runs are safe.
INSERT INTO customer (cust_id, cust_name, status) VALUES (101, 'TEST CUSTOMER 1', 'ACTIVE') ON CONFLICT (cust_id) DO NOTHING;
INSERT INTO customer (cust_id, cust_name, status) VALUES (102, 'TEST CUSTOMER 2', 'ACTIVE') ON CONFLICT (cust_id) DO NOTHING;
INSERT INTO customer (cust_id, cust_name, status) VALUES (103, 'TEST CUSTOMER 3', 'INACTIVE') ON CONFLICT (cust_id) DO NOTHING;
