#!/usr/bin/python
import argparse
import sys, time
import logging
import urllib2
import httplib #For exceptions, should fix from speedtest class
from ConfigParser import SafeConfigParser

import socket
from speedtest import Speedtest,SpeedtestError
from random import choice

#Get python-daemon version and load right module
import daemon
daemon_version = daemon._version.split(".")
while len(daemon_version) < 5: daemon_version.append(str(0))
daemon_version = int("".join(daemon_version))

if daemon_version < 16000:
	import runner155 as runner #local hacked up DaemonRunner
else:
	print "python-daemon version 1.5.5 required"
	import runner16 as runner #local hacked up DaemonRunner


try:
	import pymysql as mysql
except ImportError:
	try:
		import MySQLdb as mysql
	except ImportError:
		mysql = None

import peewee
from peewee import *
mysql_database = None
nlOptions = {}

def logAndReThrowException(logger, e):
	if logger:
		logger.error('Uncatched exception: ' + str(e))

	executionInfo = sys.exc_info()
	raise executionInfo[1], None, executionInfo[2]


#1 Main
if __name__ == "__main__":
	
	logger = None
	
	nlOptions = {}
	
	try:
		#Parser controls
		parser = argparse.ArgumentParser("./networkLogger.py")
		parser.add_argument('-c', nargs=1, help="Load alternative config file")
		parser.add_argument('-d', nargs=1, help="Daemon controls [start|stop|restart]")
		
		parser.add_argument('-s', nargs=2, help="Set sleepTime and Speedtest multiplier")
		parser.add_argument('-iss', nargs='+', help="Set InternetStatus server(s)")
		parser.add_argument('-sts', nargs='+', help="Set Speedtest server(s)")
		parser.add_argument('-nodb', nargs=1, help="Disable database []")
		
		args = parser.parse_args()
		nlOptions['args'] = args # For #2 main
		
		
		if args.s is not None:
			nlOptions['sleepTime'] = args.s[0]
			nlOptions['stMultiplier'] = args.s[1]
			
		if args.iss is not None:
			nlOptions['internetStatusServers'] = args.iss
		
		if args.sts is not None:
			nlOptions['internetSpeedtestServers'] = args.sts
		
		if args.nodb is not None:
			if args.nodb != "0" or args.nodb != "false":
				nlOptions['databaseEnabled']= False
			
		
		configParser = SafeConfigParser()
		configFile = 'config'
		if args.c is not None:
			configFile = args.c
		
		configParser.read(configFile)
		if 'sleepTime' not in nlOptions:
			nlOptions['sleepTime'] = int(configParser.get('Main','SleepTime'))
		if 'stMultiplier' not in nlOptions:
			nlOptions['stMultiplier'] = configParser.getint('Main','Multiplier')
		if 'internetStatusServers' not in nlOptions:
			nlOptions['internetStatusServers'] = configParser.get('InternetStatus','Servers').split()
		if 'internetSpeedtestServers' not in nlOptions:
			nlOptions['internetSpeedtestServers'] = configParser.get('Speedtest','Servers').split()
		if 'databaseEnabled' not in nlOptions:
			nlOptions['databaseEnabled']= True

		configParser.read(configFile)

		#DB settings
		engine = configParser.get('Database','engine')
		if engine == "mysql":
			print "Using Mysql"
			mysql_database = MySQLDatabase(configParser.get('mysql','database'), **{'passwd': configParser.get('mysql','password'), 'user':  configParser.get('mysql','username'), 'host':configParser.get('mysql','server')})
		elif engine == "sqlite":
			print "Using SQLite"
			mysql_database = SqliteDatabase( configParser.get('sqlite','database') )
		else:
			raise Exception("DB not set.")
	except Exception as e:
		logAndReThrowException(logger, e)


#ActiveRecord for NetworkStatus
class NetworkStatus2(Model):
	timestamp_first = IntegerField()
	timestamp_last = IntegerField()
	status = BooleanField()
	
	class Meta:
		database = mysql_database

#ActiveRecord for NetworkSpeed
class NetworkSpeed2(Model):
	timestamp = IntegerField()
	server = CharField()
	ping = FloatField()
	download = FloatField()
	upload = FloatField()

	class Meta:
		database = mysql_database

class NetworkStatusLogger():
	
	_options = None
	_logger = None
	_currentStatus = None
	_ns2row = None

	def __init__(self, logger=None, options={}):
		self.stdin_path = '/dev/null'
		self.stdout_path = '/dev/tty'
		self.stderr_path = '/dev/tty'
		self.pidfile_path =  '/var/run/networkStatusLogger2.pid'
		self.pidfile_timeout = 5
		self._logger = logger
		
		self._loadOptions(options)
	
	def _loadOptions(self, options):
		#Every option key
		optionKeys = ('sleepTime', 'stMultiplier', 'internetStatusServers', 'internetSpeedtestServers', 'countryCode', 'databaseEnabled')
			
		#Check missing option keys
		missingKeys = []
		for key in optionKeys:
			if key not in options:
				missingKeys.append(key)
			
		if len(missingKeys) > 0:
			default = {}
			default['sleepTime'] = 300
			default['stMultiplier'] = 6
			default['internetStatusServers'] = ['173.194.69.103']
			default['internetSpeedtestServers'] = ['auto', 'random']
			default['countryCode'] = 'FI'
			default['databaseEnabled'] = True
				
			for key in missingKeys:
				options[key] = default[key]
				
		self._options = options
		return
	
	def dbAddStatus(self):
		if self._options['databaseEnabled'] == False:
			return
			
		try:
			timeNow = int(time.time())
			doNew = False
			ns2Object = None
			
			if self._ns2row is not None:
				if self._ns2row.status == self._currentStatus:
					self._ns2row.timestamp_last = timeNow
					self._ns2row.save()
				else:
					doNew = True
			else:
				doNew = True
			
			if doNew:
				self._ns2row = NetworkStatus2.create(status=self._currentStatus, timestamp_first=int(timeNow), timestamp_last=int(timeNow))
			
			self._currentStatus = None
		
		except (mysql.DatabaseError) as e:
			pass
			#self._logger.error('dbAddStatus() exception: ' + str(e))

	
	def dbAddSpeed(self, internetSpeed):
		if self._options['databaseEnabled'] == False:
			return
		
		try:
			print internetSpeed
			dbSpeed = NetworkSpeed2()
			dbSpeed.timestamp = int(time.time())
			dbSpeed.server = internetSpeed['server']
			dbSpeed.ping = internetSpeed['ping']
			dbSpeed.download = internetSpeed['download']
			dbSpeed.upload = internetSpeed['upload']
			dbSpeed.save()
		except mysql.DatabaseError as e:
			pass
			#self._logger.error('dbAddSpeed() exception: ' + str(e))

	# Determine if Internet connection is working by xxx servers loaded from config
	# (DNS translation can take more time than timeout, that's why we are using IP address)
	def internet_on(self):
		speedtest = Speedtest()
		count = 0
		servers = self._options['internetStatusServers']
		for url in servers:
			try:
				urllib2.urlopen("http://" + str(url),timeout=5)
				count += 1
			except Exception as err:
				pass
		if count > (len(servers) / 2.0):
			print "Internet ok"
			print ""
			return True
		else:
			print "Internet down"
			print ""
			return False
	
	def getSpeeds(self, speedtest):
		try:
			results = {'ping':-1, 'download':-1, 'upload':-1, 'server':"-1"}
			#servers = ["auto", "random"]
			servers = self._options['internetSpeedtestServers']
			for url in servers:
				if url == "auto":
					speedtest.setNearestserver()
				elif url == "random":
					speedtest.setRandomServer(self._options['countryCode'])
				else:
					speedtest.setServer(host)
				
				results = self._getSpeed(speedtest)
		#except (urllib2.URLError, socket.error, socket.gaierror, httplib.BadStatusLine) as e:
		except (SpeedtestError, httplib.IncompleteRead, socket.gaierror) as e:
			pass
			#self._logger.error('getSpeeds() exception: ' + str(e))
		return results
	
	def _getSpeed(self, speedtest):
			results = {'ping':speedtest.ping(speedtest._host), 'download':speedtest.download(), 'upload':speedtest.upload(), 'server':speedtest._host}
			return results
			

	# Run method, test internet, test speed, write to local db, sleep
	def run(self):
		sleepTime = self._options['sleepTime']
		speedtest = Speedtest()
		speedtestCounter = 0
		
		while True:
			try:
				internetSpeed = None
				speedtestCounter+=1
				
				if self.internet_on():
					self._currentStatus = True
				else:
					self._currentStatus = False
    		    
				if speedtestCounter >= (self._options['stMultiplier']):
					speedtestCounter = 0
					internetSpeed = self.getSpeeds(speedtest)
					print internetSpeed

				if self._currentStatus is not None:
					self.dbAddStatus()
						
				if internetSpeed is not None:
					self.dbAddSpeed(internetSpeed)
				
				time.sleep(sleepTime)
			#TODO: add OperationalError
			except ZeroDivisionError as e:
				#print "NetworkLogger.run() exception catcher:" + str(e)
				#self._logger.error('Run() exception: ' + str(e))
				time.sleep(120)
	#/run_network_logging()

def initLogger():
	logger = logging.getLogger("DaemonLog")
	logger.setLevel(logging.INFO)
	formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
	handler = logging.FileHandler("/var/log/networkLogger.log")
	handler.setFormatter(formatter)
	logger.addHandler(handler)
	return logger

#2 Main
if __name__ == "__main__":
	try:
		args = nlOptions['args']
		if args.d is None:
			networkStatusLogger = NetworkStatusLogger( options=nlOptions )
			networkStatusLogger.run()
		else:
			logger = initLogger()
			networkStatusLogger = NetworkStatusLogger( logger, nlOptions )
			daemon_runner = runner.DaemonRunner(networkStatusLogger)
			daemon_runner.parse_args([sys.argv[0], args.d[0]])
			daemon_runner.do_action()
	except Exception as e:
		logAndReThrowException(logger, e)
	
	#eof
