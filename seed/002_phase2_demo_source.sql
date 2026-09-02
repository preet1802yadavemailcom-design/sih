-- Development-only source. It never calls an external provider.
INSERT INTO source_registry
  (source_id, source_name, source_type, access_method, authorization_status, tos_status, robots_status, metadata)
VALUES
  ('DEMO', 'APIx Local Demo', 'OTHER', 'MANUAL', 'APPROVED', 'ALLOWED', 'ALLOWED',
   '{"environment":"development","network_access":false,"note":"Synthetic source for Phase 2 tests only."}')
ON CONFLICT (source_id) DO NOTHING;
