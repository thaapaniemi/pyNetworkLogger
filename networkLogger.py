#!/usr/bin/python
import argparse
import sys, time
import logging
import urllib2
from ConfigParser import SafeConfigParser
import daemon
import runner #local hacked up DaemonRunner
import socket

from speedtest import Speedtest
from random import choice

from peewee import *
mysql_database = MySQLDatabase('my_database', **{'passwd': 'top_secret', 'user': 'database_user'})


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

	_logger = None
	_currentStatus = None
	_ns2row = None

	def __init__(self, logger=None):
		self.stdin_path = '/dev/null'
		self.stdout_path = '/dev/tty'
		self.stderr_path = '/dev/tty'
		self.pidfile_path =  '/var/run/networkStatusLogger2.pid'
		self.pidfile_timeout = 5
		
		self._logger = logger
		
	def dbAddStatus(self,okTime=600):
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

	
	def dbAddSpeed(self, internetSpeed):
		print internetSpeed
		dbSpeed = NetworkSpeed2()
		dbSpeed.timestamp = int(time.time())
		dbSpeed.server = internetSpeed['server']
		dbSpeed.ping = internetSpeed['ping']
		dbSpeed.download = internetSpeed['download']
		dbSpeed.upload = internetSpeed['upload']
		dbSpeed.save()

	# Determine if Internet connection is working by xxx servers loaded from config
	# (DNS translation can take more time than timeout, that's why we are using IP address)
	def internet_on(self):
		speedtest = Speedtest()
		count = 0
		#servers = [ "173.194.69.103", "217.149.58.162" ]
		servers = [ "192.168.10.1" ]
		for url in servers:
			try:
				urllib2.urlopen("http://" + str(url),timeout=5)
				count += 1
			except Exception as err:
				#Suppose there is better way to do this than throw-catch exceptions?
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
			servers = ["auto", "random"]
			for url in servers:
				if url == "auto":
					speedtest.setNearestserver()
				elif url == "random":
					speedtest.setRandomServer("FI")
				else:
					speedtest.setServer(host)
				
				results = self._getSpeed(speedtest)
		except (urllib2.URLError, socket.error, socket.gaierror) as e:
			self._logger.error('getSpeeds() exception: ' + str(e))
		return results
	
	def _getSpeed(self, speedtest):
		try:
			results = {'ping':speedtest.ping(speedtest._host), 'download':speedtest.download(), 'upload':speedtest.upload(), 'server':speedtest._host}
			#print results
			return results
		except (AttributeError, socket.gaierror) as e:
			self._logger.error('_getSpeed() exception: ' + str(e))
			return {'ping':-1, 'download':-1, 'upload':-1, 'server':"-1"}
			

	# Run method, test internet, test speed, write to local db, sleep
	def run(self):
		sleepTime = 30
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
    		    
				if speedtestCounter >= (1800/sleepTime):
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
				self._logger.error('Run() exception: ' + str(e))
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

if __name__ == "__main__":
	executionInfo = None # This is for re-throwed exceptions with full traceback
	logger = None
	
	try:
		#Parser controls
		parser = argparse.ArgumentParser("./networkLogger.py")
		parser.add_argument('-d', nargs=1, help="Daemon controls [start|stop|restart]")
		args = parser.parse_args()
			
		if(args.d is None):
			networkStatusLogger = NetworkStatusLogger()
			networkStatusLogger.run()
		else:
			logger = initLogger()
			networkStatusLogger = NetworkStatusLogger( logger )
			daemon_runner = runner.DaemonRunner(networkStatusLogger)
			daemon_runner.parse_args([sys.argv[0], args.d[0]])
			daemon_runner.do_action()
	except Exception as e:
		if logger:
			logger.error('Uncatched exception: ' + str(e))
		executionInfo = sys.exc_info()
	
	#Re-throw exceptions with traceback data
	if executionInfo:
		raise executionInfo[1], None, executionInfo[2]

	#eof
