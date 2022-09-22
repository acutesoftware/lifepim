#!/usr/bin/python3
# coding: utf-8
# query_DIARY.py

"""
 query_DIARY.py   written by Duncan Murray  30/7/2022


D202204.dat
D20220401000120220401PCFile0000 8UsageGroove Music
D20220401000220220401PCFile0007 6UsageGroove Music
D20220401000320220401PCFile0008 1Usageclassical music tchaikovsky - Google Search - Google Chrome
D20220401000420220401PCFile0009 1UsageGroove Music

D202106.dat
D20210608000120210608093030DATR/L
D20210608000220210608170030DATEmail about Diary running on Windows 10

wrong num columns - 
D20220125018420220125PCFile1924 1UsageLifePIM Desktop


"""

import os 
import sys
import sqlite3
path_root =  os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + ".." + os.sep + ".." ) 
sys.path.append(str(path_root))

import config as mod_cfg


path_diary = r"U:\acute\netDiary\data"
output_folder = mod_cfg.user_folder
db_name = mod_cfg.db_name

db_table_raw_data = 'raw_EVENTS'
sql = 'select date, time, reference, ActionID, details from ' + db_table_raw_data + ' WHERE date like "202205%" ORDER BY 1, 2 limit 100'

sql = 'select date, time, reference, ActionID, details from ' + db_table_raw_data + ' WHERE ActionID != "PCFile" and date like "202%" ORDER BY 1, 2 limit 100'
"""
('20211109', '1928', 'PCFile', 'Usage', 'Read CSV file in Pandas Python - Stack Overflow - Google Chrome'), 
('20211109', '1932', 'PCFile', 'Usage', 'python - How to iterate over rows in a DataFrame in Pandas - Stack Overflow - Google Chrome')]
"""

sql = 'select date, time, reference, ActionID, details from ' + db_table_raw_data + ' WHERE reference != "PCFile" and date like "202%" ORDER BY 1, 2 limit 100'
"""
[('20210608', '0930', '', '', 'R/L'), ('20210608', '0930', '', '', 'R/L'), 
('20210608', '1700', '', '', 'Email about Diary running on Windows 10'), 
]
"""

sql = 'select substr(date, 1,4) as YR, count(*) as num_recs from diary_events group by substr(date, 1,4) order by 1 desc'
"""
2022	8
2021	6
2017	1
2015	1
2014	40
2013	239
2012	331
2011	894
2010	1231
2009	1880
2008	1357
2007	2542
2006	2070
2005	2497
2004	2658
2003	2108
2002	1876
2001	1447
2000	1428
1999	3039
1995	6
1976	3
1966	1
	5
"""

sql = 'select substr(date, 1,4) as YR, count(*) as num_recs from diary_file_usage group by substr(date, 1,4) order by 1 desc'
"""
2034	88
2021	3
2013	10116
2012	25648
2011	14989
2010	31143
2009	35945
2008	39467
2007	99932
2006	48841
2005	74607
2004	48438
2003	48509
2002	33730
2001	27751
2000	18719
1999	13037
1998	6888
1997	5264
1996	2871
1995	3325
1994	2885
1993	1828
1992	1090
1991	862
1990	643
1989	377
1988	293
1987	214
1986	19
1985	8
1984	15
1983	23
1982	6
1980	86
1920	58
1919	65
1918	14
1917	38
1916	5
1914	4
1913	23
1911	1
1910	1
"""

sql = 'select substr(date, 1,4) as YR, count(*) as num_recs from diary_pc_usage group by substr(date, 1,4) order by 1 desc'
"""
[('{\\co', 2), ('PsÖZ', 1), ('2022', 42796), ('2021', 9790), ('2020', 237), ('2017', 23978), ('2014', 2101), 
 ('2013', 40133), ('2012', 41926), ('2011', 34242), ('2010', 28671), ('2009', 27783), ('2008', 24253), ('2007', 41808), 
 ('2006', 37837), ('2005', 37411), ('2004', 37963), ('2003', 44840), ('2002', 32706), ('2001', 32784), ('2000', 37046), ('1999', 2784), ('', 2)]
"""

sql = 'select substr(date, 1,4) as YR, count(*) as num_recs from diary_pc_usage WHERE details like "%AIKIF%" and length > 0 group by substr(date, 1,4) order by 1 desc'

# Blender = [('2022', 270), ('2021', 106), ('2017', 1), ('2013', 112), ('2012', 1), ('2006', 1)]
# Unreal Editor = [('2022', 7714), ('2021', 2370), ('2020', 1)]
# AIKIF = [('2022', 141), ('2021', 6), ('2017', 1790), ('2013', 264)]
def main():
    db = DataBase(db_name)
    # Run the SQL
    db.exec(sql)
    print(db.cur.fetchall())



class DataBase(object):
    def __init__(self, dbname):
        self.dbname = dbname
        self.con = sqlite3.connect(self.dbname)
        self.cur = self.con.cursor()

    def exec(self, sql_text):
        self.cur.execute(sql_text)
        self.con.commit()
        
    def close(self):
        self.con.close()


main()