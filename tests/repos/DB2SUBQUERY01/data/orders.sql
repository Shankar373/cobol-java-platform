-- DB2SUBQUERY01 per-repo seed: WHERE amount > 500 subquery needs order with amount=1000
-- Idempotent: ON CONFLICT DO NOTHING so re-runs are safe.
INSERT INTO orders (order_id, customer_id, amount) VALUES (1, 101, 1000) ON CONFLICT (order_id) DO NOTHING;
INSERT INTO orders (order_id, customer_id, amount) VALUES (2, 102, 200) ON CONFLICT (order_id) DO NOTHING;
