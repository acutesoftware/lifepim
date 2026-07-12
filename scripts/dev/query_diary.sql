
select * from lp_calendar_events -- 4 rowa

select * from lp_calendar_day_stats -- 0 rows

select * from lp_calendar_item_days order by calendar_item_id

select * from lp_calendar_events where id = 270
-- 270	Bins		2026-07-15 17:00		house			2026-07-15	17:00	2026-07-15	17:00	0	0	event	None	active	None		None	None	FREQ=WEEKLY;INTERVAL=2	2026-07-15			manual		2026-07-11T12:22:34Z	2026-07-11T12:23:25Z


select * from lp_calendar_items where source_record_id = 270
-- 11293	2	recurring	270		recurring:270:2026-07-15	270	event	Bins		2026-07-15	17:00	2026-07-15	17:00	0	0	event	None	house	active	None		None	None	20	1	calendar.view_event_route	270	2026-07-11T12:23:25Z	2026-07-11T12:33:21Z
-- 11294	2	recurring	270		recurring:270:2026-07-29	270	event	Bins		2026-07-29	17:00	2026-07-29	17:00	0	0	event	None	house	active	None		None	None	20	1	calendar.view_event_route	270	2026-07-11T12:23:25Z	2026-07-11T12:33:21Z
-- 11295	2	recurring	270		recurring:270:2026-08-12	270	event	Bins		2026-08-12	17:00	2026-08-12	17:00	0	0	event	None	house	active	None		None	None	20	1	calendar.view_event_route	270	2026-07-11T12:23:25Z	2026-07-11T12:33:21Z
-- ...

select * from lp_calendar_sources

/*
1	manual	Manual Events	event	1	1	#1f77b4	#ffffff	calendar	10	immediate			2026-07-11T12:22:34Z	current	Projected manual event.	1			2026-07-11T11:24:15Z
2	recurring	Recurring Events	generated	1	1	#9467bd	#ffffff	repeat	20	rebuild	730	3650	2026-07-11T12:33:21Z	current		532			2026-07-11T11:24:15Z
3	birthdays	Birthdays	generated	1	1	#e377c2	#ffffff	cake	30	rebuild	0	7300				0			2026-07-11T11:24:15Z
4	holidays_au	Australian Public Holidays	imported	1	1	#2ca02c	#ffffff	flag	40	rebuild	1825	3650				0			2026-07-11T11:24:15Z
5	holidays_sa	South Australian Public Holidays	imported	1	1	#17becf	#ffffff	flag	41	rebuild	1825	3650				0			2026-07-11T11:24:15Z
6	tasks	Task Deadlines	linked	1	0	#d62728	#ffffff	deadline	50	incremental						0			2026-07-11T11:24:15Z
7	files	File Activity	metadata	0	0	#7f7f7f	#ffffff	file	100	incremental						0			2026-07-11T11:24:15Z
8	media	Photos and Videos	metadata	0	0	#ff7f0e	#ffffff	image	90	incremental						0			2026-07-11T11:24:15Z
9	audio	Audio	metadata	0	0	#bcbd22	#111111	music	90	incremental						0			2026-07-11T11:24:15Z
10	usage	Usage	log	0	0	#8c564b	#ffffff	activity	100	incremental						0			2026-07-11T11:24:15Z

*/


select reference, count(*) from diary_events group by reference order by 2 desc;

select * from diary_events where reference = 'Visit';

select 'diary_raw' as tbl, count(*) as num_recs from diary_raw UNION ALL
select 'diary_events' as tbl, count(*) as num_recs from diary_events UNION ALL
select 'diary_pc_usage' as tbl, count(*) as num_recs from diary_pc_usage UNION ALL
select 'diary_file_usage' as tbl, count(*) as num_recs from diary_file_usage;

/*
diary_raw			734502
diary_events		 16815
diary_pc_usage		313051
diary_file_usage	404636
*/



select * from lp_notes
