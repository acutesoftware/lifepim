import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

metadata_database = r"C:\DATA\filelist_master.db"

conn = sqlite3.connect(metadata_database)

# Query cumulative sizes in kB
df = pd.read_sql_query("""
SELECT 
  substr(modified, 1, 4) AS year,
  ROUND(SUM(SUM(size)) OVER (ORDER BY substr(modified, 1, 4)) / 1024.0, 2) AS cum_kB
FROM s_files
WHERE modified >= '1981-01-01' AND modified < '2030-01-01'
                         AND pth NOT LIKE 'C:%'
GROUP BY substr(modified, 1, 4)
ORDER BY year;
""", conn)

# Plot
fig, ax = plt.subplots(figsize=(10,6))
ax.bar(df["year"], df["cum_kB"])
ax.set_yscale('log')
ax.set_xlabel("Year")
ax.set_ylabel("Cumulative size")

# Add friendly labels (kB, MB, GB, TB)
def human_format(x, pos):
    if x < 1e3:
        return f"{x:g} kB"
    elif x < 1e6:
        return f"{x/1e3:g} MB"
    elif x < 1e9:
        return f"{x/1e6:g} GB"
    else:
        return f"{x/1e9:g} TB"

ax.yaxis.set_major_formatter(mticker.FuncFormatter(human_format))
ax.set_title("Total File Size Over Time (user files, photos, documents, etc.)")


ax.grid(which='major', axis='y', linestyle='--', alpha=0.6)
ax.set_xticks(df["year"][::2])  # show every 2nd year

plt.xticks(rotation=45, ha='right')

plt.tight_layout()
plt.savefig("chart_file_size_over_time.png", dpi=300, bbox_inches='tight')
plt.show()
