import sys

import urllib
import httplib
import getopt
import bisect
import re
import random

from time import time
from threading import Thread, currentThread
from math import pow, sqrt
from xml.dom import minidom

# Speedtest Exception class
class SpeedtestError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

#Speedtest class
class Speedtest:
	_host = None
	_runs = 2
	_verbose = 0
	_httpdebug = 0
	
	_download_files = [
	'/speedtest/random350x350.jpg',
	'/speedtest/random500x500.jpg',
	'/speedtest/random1500x1500.jpg',
	]
	
	_upload_files = [
	132884,
	493638
	]
	
	# Serverlist of all public Speedtest servers
	_serverscc = None
	_servers = None

	# Use best server
	def setNearestserver(self):
		self._host = self._setNearestServer()

	# Use random server, limit by country code (ISO 3166-1 alpha-2)
	def setRandomServer(self, cc=None):
		if(self._servers is None or self._serverscc != cc):
			self._servers = self._getServerList(cc)
			self._serverscc = cc
		self._host = random.choice(self._servers)
	
	# Use any server specified
	def setServer(self, newServer):
		self._host = newServer
		
	# Test download speed, returns speed in bps
	def download(self):
		try:
			if self._host is None:
				self._host = self.chooseserver()
		
			total_downloaded = 0
			connections = []
			for run in range(self._runs):
				connection = httplib.HTTPConnection(self._host)
				connection.set_debuglevel(self._httpdebug)
				connection.connect()
				connections.append(connection)
			total_start_time = time()
			for current_file in self._download_files:
				threads = []
				for run in range(self._runs):
					thread = Thread(target = self._downloadthread, args = (connections[run], current_file + '?x=' + str(int(time() * 1000))))
					thread.run_number = run
					thread.start()
					threads.append(thread)
				for thread in threads:
					thread.join()
					total_downloaded += thread.downloaded
					#self._printv('Run %d for %s finished' % (thread.run_number, current_file))
			total_ms = (time() - total_start_time) * 1000
			for connection in connections:
				connection.close()
			#self._printv('Took %d ms to download %d bytes' % (total_ms, total_downloaded))
			return (total_downloaded * 8000 / total_ms)
		except Exception as e:
			raise SpeedtestError(e)
	
	# Test upload speed, returns speed in bps
	def upload(self):
		try:
			if self._host is None:
				raise SpeedtestError('Host not set.')
			
			connections = []
			for run in range(self._runs):
				connection = httplib.HTTPConnection(self._host)
				connection.set_debuglevel(self._httpdebug)
				connection.connect()
				connections.append(connection)
				
			post_data = []
			ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
			for current_file_size in self._upload_files:
				values = {'content0' : ''.join(random.choice(ALPHABET) for i in range(current_file_size)) }
				post_data.append(urllib.urlencode(values))
				
			total_uploaded = 0
			total_start_time = time()
			for data in post_data:
				threads = []
				for run in range(self._runs):
					thread = Thread(target = self._uploadthread, args = (connections[run], data))
					thread.run_number = run
					thread.start()
					threads.append(thread)
				for thread in threads:
					thread.join()
					#self._printv('Run %d for %d bytes finished' % (thread.run_number, thread.uploaded))
					total_uploaded += thread.uploaded
			total_ms = (time() - total_start_time) * 1000
			for connection in connections:
				connection.close()
			#self._printv('Took %d ms to upload %d bytes' % (total_ms, total_uploaded))
			return (total_uploaded * 8000 / total_ms)
		except Exception as e:
			raise SpeedtestError(e)
	
	#Test ping time, returns response time in ms
	def ping(self,host=None, tries=5):
		try:
			#Set pinging to selected server if not specified
			if host is None:
				if self._host is None:
					raise SpeedtestError('Host not set.')
				host = self._host
				
			connection = httplib.HTTPConnection(host)
			connection.set_debuglevel(self._httpdebug)
			connection.connect()
			times = []
			worst = 0
			for i in range(tries):
				total_start_time = time()
				connection.request('GET', '/speedtest/latency.txt?x=' + str(random.random()), None, { 'Connection': 'Keep-Alive'})
				response = connection.getresponse()
				response.read()
				total_ms = time() - total_start_time
				times.append(total_ms)
				if total_ms > worst:
					worst = total_ms
			times.remove(worst)
			total_ms = sum(times) * 250 # * 1000 / number of tries (4) = 250
			connection.close()
			#self._printv('Latency for %s - %d' % (host, total_ms))
			return total_ms
		except Exception as e:
			raise SpeedtestError(e)
	
	# Automatically selects best server, returns server address
	def _setNearestServer(self):
		connection = httplib.HTTPConnection('www.speedtest.net')
		connection.set_debuglevel(self._httpdebug)
		connection.connect()
		now = int(time() * 1000)
		extra_headers = {
			'Connection': 'Keep-Alive',
			'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.7; rv:10.0.2) Gecko/20100101 Firefox/10.0.2',
		}
		connection.request('GET', '/speedtest-config.php?x=' + str(now), None, extra_headers)
		response = connection.getresponse()
		reply = response.read()
	 	m = re.search('<client ip="([^"]*)" lat="([^"]*)" lon="([^"]*)"',reply)
		location = None
		if m == None:
			#self._printv("Failed to retrieve coordinates")
			raise SpeedtestError('method chooseserver: Failed to retrieve coordinates')
		location = m.groups()
		#self._printv('Your IP: %s\nYour latitude: %s\nYour longitude: %s' % location)
		connection.request('GET', '/speedtest-servers.php?x=' + str(now), None, extra_headers)
		response = connection.getresponse()
		reply = response.read()
		server_list = re.findall('<server url="([^"]*)" lat="([^"]*)" lon="([^"]*)"', reply)
		my_lat = float(location[1])
		my_lon = float(location[2])
		sorted_server_list = []
		for server in server_list:
			s_lat = float(server[1])
			s_lon = float(server[2])
			distance = sqrt(pow(s_lat - my_lat,2) + pow(s_lon - my_lon, 2))
			bisect.insort_left(sorted_server_list,(distance, server[0]))
		best_server = (999999, '')
		for server in sorted_server_list[:10]:
			m = re.search('http://([^/]+)/speedtest/upload\.php',server[1])
			if not m : continue
			server__host = m.groups()[0]
			latency = self.ping(server__host)
			if latency < best_server[0]:
				best_server = (latency, server__host)
		return best_server[1]
	
	# Downloads and parses list of speedtest servers, returns list
	# Limit list by 2-letter country code
	def _getServerList(self,cc=None):
		serverlist = []
		# XML- list of servers http://speedtest.net/speedtest-servers.php
		#serverXMLlist = urllib2.urlopen("http://speedtest.net/speedtest-servers.php", timeout=10).read()
		serverXMLlist = urllib.urlopen("http://speedtest.net/speedtest-servers.php").read()
		xmldoc = minidom.parseString(serverXMLlist)
		itemlist = xmldoc.getElementsByTagName('server')
		for t_url in itemlist:
			if(cc is None):
				pass #If no cc selected no need to do anything
			elif(t_url.attributes['cc'].value != cc):
				continue #If not cc wanted break this loop and continue

			# Clean the string to get bare address
			t_url = t_url.attributes['url'].value
			t_url = t_url.replace("/speedtest/upload.php", "")
			t_url = t_url.replace("http://", "")
			t_url = t_url.split("/")[0]
			serverlist.append(t_url)
		return serverlist
	
	# Private function for verbose stdout printing
	def _printv(self,msg):
		if self._verbose : print msg
	
	def _downloadthread(self,connection, url):
		connection.request('GET', url, None, { 'Connection': 'Keep-Alive'})
		response = connection.getresponse()
		self_thread = currentThread()
		self_thread.downloaded = len(response.read())

	def _uploadthread(self,connection, data):
		url = '/speedtest/upload.php?x=' + str(random.random())
		connection.request('POST', url, data, {'Connection': 'Keep-Alive', 'Content-Type': 'application/x-www-form-urlencoded'})
		response = connection.getresponse()
		reply = response.read()
		self_thread = currentThread()
		self_thread.uploaded = int(reply.split('=')[1])
		
#/Speedtest
