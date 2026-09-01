-- DB2LEFTJOIN01 per-repo seed: LEFT JOIN test uses dept table for join
-- dept_id=10 'ENGINEERING'; customer 101 has dept_id=NULL → LEFT JOIN returns NULL
-- Idempotent: ON CONFLICT DO NOTHING so re-runs are safe.
INSERT INTO dept (dept_id, dept_name) VALUES (10, 'ENGINEERING') ON CONFLICT (dept_id) DO NOTHING;
