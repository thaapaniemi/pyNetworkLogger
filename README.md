# pyNetworkLogger

2013 Tomi Haapaniemi, [firstname].[lastname]@metropolia.fi

NetworkLogger monitors network healt by trying to connect to (predefined) server and run speedtest periodically.
Results are then logged to database.

Can be run as standalone or as daemon (requires root).

Requirements: python-daemon-1.5.5, peewee

Todo: 
* config file support. 
* More commandline-options.
* Change to support or use python-daemon-1.6

usage: ./networkLogger.py [-h] [-c C] [-d D] [-s S S] [-iss ISS [ISS ...]]
                          [-sts STS [STS ...]]

optional arguments:
  -h, --help          show this help message and exit
  -c C                Load alternative config file
  -d D                Daemon controls [start|stop|restart]
  -s S S              Set sleepTime and Speedtest multiplier
  -iss ISS [ISS ...]  Set InternetStatus server(s)
  -sts STS [STS ...]  Set Speedtest server(s)

