-- DB2JOIN01 per-repo seed: INNER JOIN test requires CUSTOMER(101) + ORDERS(1->101)
-- Idempotent: ON CONFLICT DO NOTHING so re-runs are safe.
INSERT INTO customer (cust_id, cust_name) VALUES (101, 'TEST CUSTOMER') ON CONFLICT (cust_id) DO NOTHING;
