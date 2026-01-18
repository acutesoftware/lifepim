@echo off
ECHO Run order 
ECHO 1. init_database.py
ECHO 2. Load sample data.  python LOAD_TESTING.py
ECHO 3. Run ETL_MAP_FOLDERS.BAT (now also backfills folder_id).
ECHO user_folder = r"D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data"

python etl_folder_mapping.py ^
  --db D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data\lifepim.db ^
  --folders_csv E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\all_folders.csv ^
  --rules_csv E:\BK_fangorn\user\duncan\LifePIM_Data\configuration\map_project_folder.csv
