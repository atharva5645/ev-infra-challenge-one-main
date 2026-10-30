-- Illustrative prototype records only. These are synthetic examples and are
-- not official government statistics or verified station listings.

INSERT INTO states (state_code, state_name) VALUES
    ('IN-KA', 'Karnataka'),
    ('IN-MH', 'Maharashtra');

INSERT INTO districts (district_code, state_code, district_name) VALUES
    ('IN-KA-BLRU', 'IN-KA', 'Bengaluru Urban'),
    ('IN-KA-MYS', 'IN-KA', 'Mysuru'),
    ('IN-MH-PUN', 'IN-MH', 'Pune'),
    ('IN-MH-NAG', 'IN-MH', 'Nagpur');

INSERT INTO charger_source_records
    (source_name, source_record_key, station_name, district_code, latitude, longitude, charger_type, recorded_at, raw_attributes)
VALUES
    ('Illustrative seed dataset', 'SEED-KA-001', 'Central Bengaluru Example', 'IN-KA-BLRU', 12.971600, 77.594600, 'DC fast', '2025-01-15T00:00:00Z', '{"connectors": 2}'::jsonb),
    ('Illustrative seed dataset', 'SEED-MH-001', 'Pune Example Station', 'IN-MH-PUN', 18.520400, 73.856700, 'AC', '2025-01-15T00:00:00Z', '{"connectors": 4}'::jsonb),
    ('Illustrative seed dataset', 'SEED-KA-002', 'Mysuru Example Station', 'IN-KA-MYS', 12.295800, 76.639400, 'DC fast', '2025-01-15T00:00:00Z', '{"connectors": 1}'::jsonb);

INSERT INTO chargers_unified
    (station_name, district_code, latitude, longitude, charger_type, source_name, source_record_id, confidence_score)
SELECT station_name, district_code, latitude, longitude, charger_type, source_name, source_record_id,
       CASE source_record_key WHEN 'SEED-KA-001' THEN 0.95 WHEN 'SEED-MH-001' THEN 0.90 ELSE 0.88 END
FROM charger_source_records
WHERE source_name = 'Illustrative seed dataset';

INSERT INTO ev_registrations (district_code, vehicle_class, reporting_period, ev_count, source_name) VALUES
    ('IN-KA-BLRU', 'Two-wheeler', '2025-01-01', 1200, 'Illustrative seed dataset'),
    ('IN-KA-BLRU', 'Four-wheeler', '2025-01-01', 340, 'Illustrative seed dataset'),
    ('IN-KA-MYS', 'Two-wheeler', '2025-01-01', 310, 'Illustrative seed dataset'),
    ('IN-MH-PUN', 'Four-wheeler', '2025-01-01', 520, 'Illustrative seed dataset'),
    ('IN-MH-NAG', 'Two-wheeler', '2025-01-01', 260, 'Illustrative seed dataset');

INSERT INTO hex_metrics (cell_id, reporting_period, ev_demand, charger_count, coverage, gap_score) VALUES
    ('seed-cell-blru-01', '2025-01-01', 820, 1, 0.25000, 0.75000),
    ('seed-cell-mys-01', '2025-01-01', 190, 1, 0.50000, 0.50000),
    ('seed-cell-pun-01', '2025-01-01', 410, 1, 0.30000, 0.70000),
    ('seed-cell-nag-01', '2025-01-01', 160, 0, 0.00000, 1.00000);

INSERT INTO candidate_sites
    (site_name, district_code, latitude, longitude, estimated_cost_inr, suitability_score, notes)
VALUES
    ('Bengaluru Example Candidate A', 'IN-KA-BLRU', 12.935200, 77.624500, 2500000.00, 0.87000, 'Illustrative candidate near a high-demand sample cell.'),
    ('Pune Example Candidate A', 'IN-MH-PUN', 18.507400, 73.807700, 2100000.00, 0.81000, 'Illustrative candidate for prototype planning.'),
    ('Nagpur Example Candidate A', 'IN-MH-NAG', 21.145800, 79.088200, 1800000.00, 0.79000, 'Illustrative candidate in a sample cell with no listed charger.');

INSERT INTO assumptions (parameter_name, parameter_value, units, description, source) VALUES
    ('planning_horizon_years', 5, 'years', 'Illustrative horizon used for prototype planning examples.', 'Prototype default; editable assumption'),
    ('target_chargers_per_1000_evs', 2.5, 'chargers per 1000 EVs', 'Illustrative planning target; not a policy standard.', 'Prototype default; editable assumption'),
    ('default_site_cost_inr', 2000000, 'INR per site', 'Illustrative default site cost for early scenarios.', 'Prototype default; editable assumption'),
    ('minimum_confidence_score', 0.70, 'score from 0 to 1', 'Illustrative threshold for records retained in a prototype view.', 'Prototype default; editable assumption');

INSERT INTO optimizer_runs
    (run_name, budget_inr, objective, recommended_sites, estimated_new_chargers, estimated_coverage_gain)
VALUES
    ('Illustrative starter scenario', 5000000.00,
     'Prioritize high-suitability candidates while improving sample coverage.',
     '[1, 2]'::jsonb, 2, 0.12000);
