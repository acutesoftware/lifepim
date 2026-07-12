-- Delete dummy rows created by old test/load scripts.
-- Review counts first if desired.

DELETE FROM lp_notes
WHERE file_name LIKE 'note_%'
  AND path = 'C:\\Notes';

DELETE FROM lp_tasks
WHERE title LIKE 'task_%';

DELETE FROM lp_calendar_events
WHERE title LIKE 'event_%'
   OR project = 'LoadTest';

-- Calendar stage-2 projected/index rows for deleted manual events.
DELETE FROM lp_calendar_items
WHERE source_key IN ('manual', 'recurring')
  AND source_record_id NOT IN (
    SELECT CAST(id AS TEXT) FROM lp_calendar_events
  );

DELETE FROM lp_calendar_item_days
WHERE calendar_item_id NOT IN (
  SELECT id FROM lp_calendar_items
);

COMMIT;