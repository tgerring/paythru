# paythru

## Assumptions

* MySQL is the database backend and has had lib/db_mysql.sql run in an empty database
* bitcoind JSON RPC interface is available. This means you have the original client running either on the same server (not recommended) or another server (preferred)
* The application is targeted at python 2.7
* **IT IS HIGHLY RECOMMENDED TO ENCRYPT YOUR WALLET FILE WITH A PASSWORD. THIS PASSWORD CAN BE SPECIFIED IN app.yaml**

## Usage

* config/app.yaml and referenced configuration files are the main ways to affect the application's behavior
* api.py is a WGSI-compatible script that can be run standalone for debugging through the built-in web.py http server for debugging or through any wsgi-compatible web server. This document assumes mod_wsgi on Apache
* Configure config/routes.yaml to map a regular expression to a Python class within api.py

## Installation

This package makes use of Python's setuptools. Simply run `python setup.py install` to install the prerequisites. If you with to distribute the package to another server, you can use `python setup.py sdist` to bundle the contents into an archive.

The application can run locally for development/debugging with the command `python api.py`. For installation on a server, an example Apache vhost file is provided as vhostconfig.conf. Modify this to suit your environment, and ensure `.htaccess` is placed in the DocumentRoot for clients to query resources from other domains.

The application includes connectivity checks where possible on startup, so if the web server throws an internal error, check the server ErrorLog for the problem. Often there are permission issues with file locations or a misconfiured account for external systems like the database.

## Configuration

By default, the application looks for `config/routes.yaml` as the entrypoint for other configuration files. This is not configurable from the command line, but could be modified as such. It is recommended to place the configuration files (especially those containing sensitive API keys such as app.yaml) in a secured location outside the web directory and under strict permissions. An more secure alternative would be to place these on a separate, encypted partition requiring manual decryption at book with a user-supplied key. **Please take care with the security of configuration files, as it contains information allowing the theft of bitcoins.**

 Why routes.yaml and not app.yaml? app.yaml contains lots of sensitive information and should be secured appropriately. There is little-to-no information in routes.yaml that would allow an attacker to significantly compromise this application's functionality. In an attempt to make securing app.yaml easier for a novice user, a path to the rest of the configuration files starts there and can easily be modified to another location by changing `appconfigpath: config/app.yaml` to some other path such as `appconfigpath: /encrytedvolume/config/app.yaml`

 To support the price conversion embedded in the website itself, a cron job runs crontab.sh to retrieve prices from a third-party service and POST the results to this application as configiured in routes.yaml. Currently, the application writes these values to a text file due to the inability of web.py to share information between threads. Using a more mature framework could allow this information to exist in memory and be shared between processes, which would preferrable from an efficiency standpoints.


