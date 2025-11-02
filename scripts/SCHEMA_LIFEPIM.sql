-- SCHEMA_LIFEPIM.sql       written by Duncan Murray 2/11/2025



CREATE TABLE IF NOT EXISTS "sys_cat_widgets" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
	"widget"	TEXT,
	"html_pre"	TEXT,
	"html_post"	TEXT,
    "notes"    TEXT
);

insert into sys_cat_widgets (widget, html_pre, html_post, notes) values
('Label', '<label>', '</label>', 'Simple text label'),
('TEXTBOX', '<input type="text" value="', '">', 'Single line text input box'),
('TEXTAREA', '<textarea>', '</textarea>', 'Multi-line text area input box'),
('DATEPICKER', '<input type="date" value="', '">', 'Date picker input box'),
('DATETIMEPICKER', '<input type="datetime-local" value="', '">', 'Date and time picker input box');


CREATE TABLE IF NOT EXISTS "sys_meta_tables" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
	"tbl"	TEXT,
	"desc_name"	TEXT,
);

INSERT INTO "sys_meta_tables" ("tbl", "desc_name") VALUES
('contacts', 'Contacts'),
('tasks', 'Tasks'),
('events', 'Events'),
('notes', 'Notes'),
('files', 'Files');


CREATE TABLE IF NOT EXISTS "sys_meta_cols" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
	"tbl"	TEXT,
	"col_name"	TEXT,
	"data_type"	TEXT DEFAULT 'TEXT',
	"display_widget"	TEXT DEFAULT 'Label',
	"display_length_max"	INTEGER DEFAULT 80,
	"edit_widget"	TEXT DEFAULT 'TEXTBOX'
);

-- Contacts table metadata
INSERT INTO sys_meta_cols ("tbl", "col_name", "data_type", "display_widget", "display_length_max", "edit_widget") VALUES
('contacts', 'first_name', 'TEXT', 'Label', 50, 'TEXTBOX'),
('contacts', 'last_name', 'TEXT', 'Label', 50, 'TEXTBOX'),
('contacts', 'date_updated', 'TEXT', 'Label', 10, 'DATEPICKER'),


-- Tasks table metadata
('tasks', 'due_date', 'DATE', 'Label', 10, 'DATEPICKER'),
('tasks', 'details', 'TEXT', 'Label', 10, 'TEXTBOX'),
('tasks', 'date_updated', 'TEXT', 'Label', 10, 'DATEPICKER'),

-- Events table metadata
('events', 'details', 'TEXT', 'Label', 100, 'TEXTBOX'),
('events', 'location', 'TEXT', 'Label', 100, 'TEXTBOX'), 
('events', 'date', 'DATETIME', 'Label', 16, 'DATETIMEPICKER'),
('events', 'date_updated', 'TEXT', 'Label', 10, 'DATEPICKER'),

-- Notes table metadata
('notes', 'title', 'TEXT', 'Label', 80, 'TEXTAREA'),
('notes', 'content', 'TEXT', 'Label', 500, 'TEXTAREA'),
('notes', 'date_updated', 'TEXT', 'Label', 10, 'DATEPICKER');


