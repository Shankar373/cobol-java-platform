-- DB2SUBQUERY01 per-repo seed: WHERE cust_id IN (SELECT customer_id FROM orders WHERE amount > 500)
-- Needs customer 101 with order amount=1000 (> 500) to be found.
-- Idempotent: ON CONFLICT DO NOTHING so re-runs are safe.
INSERT INTO customer (cust_id, cust_name) VALUES (101, 'TEST CUSTOMER') ON CONFLICT (cust_id) DO NOTHING;
INSERT INTO customer (cust_id, cust_name) VALUES (102, 'ANOTHER CUSTOMER') ON CONFLICT (cust_id) DO NOTHING;
