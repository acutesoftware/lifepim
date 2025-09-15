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
