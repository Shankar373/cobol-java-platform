-- DB2JOIN01 per-repo seed: INNER JOIN test requires ORDERS(1, customer_id=101, 2024-01-15)
-- Idempotent: ON CONFLICT DO NOTHING so re-runs are safe.
INSERT INTO orders (order_id, customer_id, order_date) VALUES (1, 101, '2024-01-15') ON CONFLICT (order_id) DO NOTHING;
