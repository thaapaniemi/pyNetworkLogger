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

>Usage: ./networkLogger.py [-h] [-d D]
>
>optional arguments:
>
>  -h, --help  show this help message and exit
>
>  -d D        Daemon controls [start|stop|restart]
>


