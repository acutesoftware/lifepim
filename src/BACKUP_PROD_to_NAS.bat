echo "backing up PROD data to NAS"
echo "ROOT_DIR=D:\DATA_LLM\dev\lifepim-desktop"
echo "PROD_DIR=C:\apps\LifePIM_Prod"

robocopy C:\apps\LifePIM_Prod\logs N:\duncan\C\dev\DATA_LLM /E /LOG:N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_PROD\bk_lp_prod_logs.log /np /R:3

robocopy D:\DATA_LLM\SAMPLE_DATA\lifepim_desktop_data N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_PROD /E /LOG:N:\duncan\LifePIM_Data\DATA\SQL\LifePIM_PROD\bk_lp_prod_dbase.log /np /R:3

echo Backup complete. Log saved to %SRC%\backup_log.txt