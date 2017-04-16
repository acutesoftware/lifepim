# LifePIM

##### Personal Information Manager for Life (Planning)

API and sample web application for long term personal information management.<br />

The web interface will allow you to run local data collection and gathering tools.
 

### Key Programs (NOT YET IMPLEMENTED)
|Filename | description |
 --- | ---      
|go_web_lifepim.bat | starts the web server for the LifePIM application|
|LP_CLI.py		  | Command Line interface to add and query data|

## Quick Start
This github repository [https://github.com/acutesoftware/lifepim](https://github.com/acutesoftware/lifepim) contains the latest code, but the current public release is available via

`pip install lifepim`

To start the API server use `lifepim/api_main.py` and run the `tests/test_api.py`

```
 * Running on http://127.0.0.1:5000/
 * Restarting with reloader
127.0.0.1 - - [28/May/2015 19:22:49] "GET /facts HTTP/1.1" 200 -
127.0.0.1 - - [28/May/2015 19:22:49] "GET /help HTTP/1.1" 200 -
127.0.0.1 - - [28/May/2015 19:22:49] "GET /users/1 HTTP/1.1" 200 -
```

 To start the web interface use `aikif/web_app/web_lifepim.py` or the batch file `lifepim\go_web_lifepim`
 


### More Information

TODO