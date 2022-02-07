## Notes on Interface folder
This is where the applications and utilities live to interface with the user

###lp_interface
base class for the interface - not implemented yet, and may not be

###file_system
File utilities mainly for collecting metadata from local filesystems
and indexing.

run via src/run_filelister.bat

###web (local flask application)
This is a local flask application, based on the live lifepim.com website.
It is not implemented, except for search via the filelister results

run via src/run_server.bat


###network - TODO API
not yet implemented

###database - TODO
scripts for managing via a database - you should be able to access all data
including adding via PLSQL functions
