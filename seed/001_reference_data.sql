INSERT INTO source_registry (source_id, source_name, source_type, access_method, authorization_status, tos_status, robots_status, metadata)
VALUES
('SRC-01','IndiGo (6E)','AIRLINE','OFFICIAL_API','PENDING','RESTRICTED','UNKNOWN','{"note":"Use official NDC/partner access; no public-site scraping fallback."}'),
('SRC-02','Air India (AI)','AIRLINE','PARTNER_API','PENDING','PROHIBITED','UNKNOWN','{"note":"Use authorized NDC/partner access only."}')
ON CONFLICT (source_id) DO NOTHING;

INSERT INTO routes (origin_iata,destination_iata,domestic) VALUES
('DEL','BOM',TRUE),('DEL','BLR',TRUE),('BOM','BLR',TRUE),('DEL','CCU',TRUE),('BLR','HYD',TRUE),('MAA','DEL',TRUE),('BLR','CCU',TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO methodology_versions (methodology_version,name,formula,rules) VALUES
('P1.0','APIx Phase 1 Canonical Data Contract','N/A','{"index_computation":"phase_2","missing_price":"explicit_status","raw_data":"append_only"}')
ON CONFLICT DO NOTHING;
