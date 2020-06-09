## Notes on Source Code for LifePIM Desktop


### Setup for your data

For your data, modify the config.py as follows 

```

user_folder = 'D:\\dev\\src\\lifepim\\lifepim\\SAMPLE_DATA'

display_name = 'Duncan'  # single user server runs on users local file system


logon_file = os.path.join(user_folder, 'configuration', 'lifepim.par')
data_folder = os.path.join(user_folder, 'DATA')
index_folder = os.path.join(user_folder, 'index')

```

Basically you need 3 subfolders under your main data folder
configuration = config files, passwords, etc
DATA = main data folder (each subfolder is a "Folder" in LifePIM)
index = the index files


### Index

run index.py to test against the sample data 

```

rebuilding indexes in  D:\dev\src\lifepim\lifepim\SAMPLE_DATA\index
scanning  D:\dev\src\lifepim\lifepim\SAMPLE_DATA\DATA
indexing  D:\dev\src\lifepim\lifepim\SAMPLE_DATA\DATA\blogs\Checklist for building a business website.txt
indexing  D:\dev\src\lifepim\lifepim\SAMPLE_DATA\DATA\blogs\Different ways to use folders to store your data.txt
indexing  D:\dev\src\lifepim\lifepim\SAMPLE_DATA\DATA\ideas\Different ways to use folders to store your data.txt
indexing  D:\dev\src\lifepim\lifepim\SAMPLE_DATA\DATA\recipes\Sausage Rolls with Shortcrust Pastry.txt
indexing  D:\dev\src\lifepim\lifepim\SAMPLE_DATA\DATA\work\TODO - setup wiki pages.txt
Total Files =  5
Total headings =  19
Total Hashtags =  3
Total lines =  333
Total keywords =  999
Hashtags =  ['renovations', 'health', 'TODO']

```

