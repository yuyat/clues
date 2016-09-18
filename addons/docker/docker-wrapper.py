#!/usr/bin/python
import requests
import logging
import json
import sys
import re
import threading
from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer


PORT_NUMBER = 8880
REQUEST = 0

if len(sys.argv) < 7:
  print "####ERROR####"
  print "Need docker parameters"
  print "Try: python docker-wrapper.py 3376 `docker-machine env manager`"
  sys.exit(0)
elif 'DOCKER_HOST' not in sys.argv[5] or 'DOCKER_CERT_PATH' not in sys.argv[7]:
  print "####ERROR####"
  print "####WRONG PARAMETERS####"
  sys.exit(0)

cert = '/cert.pem'
key  = '/key.pem'
IPDOCKER = '192.168.99.100:3376'
CRETEPATH = '/v1.24/containers/create'
FAKE_ID_CONTAINER = 'dc90e51d9e4c363725b82baecd84f9548810c9a8d934fa3151ac3d3b179f4657'
JOBS_P = []
timer = False

try:
  IPDOCKER=str(sys.argv[5]).split('/')[2].split(":")[0]+":"+str(sys.argv[1])
  path = str(sys.argv[7]).split('=')[1]
  cert = (path+cert).replace("\"", "")
  key = (path+key).replace("\"", "")
except:
  print "####ERROR2####"
  print "####WRONG PARAMETERS####"
  sys.exit(0)

print "SWARM IP: "+ IPDOCKER
print "CERT: "+cert
print "KEY: "+key

class myHandler(BaseHTTPRequestHandler):

  def add_JOB(self):
    global JOBS_P
    global timer
    JOB = {}
    JOB["Status"] = "pending"
    JOB["Data"] = self.rfile.readline().strip()
    JOBS_P.append(JOB)
    print "add_JOB"
    print "TOTAL: "+str(len(JOBS_P))
    if timer == False:
      timer = True
      t = threading.Timer(5.0, self.send_JOB)
      t.daemon = True
      t.start()
    return

  def num_JOBS(self):
    global JOBS_P
    self.send_response(200)
    self.send_header("Content-Type","text/plain")
    self.end_headers()
    self.wfile.write(str(len(JOBS_P)))
    print "TOTAL: "+str(len(JOBS_P))
    return

  def list_JOBS(self):
    global JOBS_P
    JOBS_R = []
    data = self.list_CONTAINERS()
    for con in data:
      JOB = {}
      JOB["Status"] = "attended"
      JOB["Data"] = con
      JOBS_R.append(JOB)
    LIST = JOBS_R + JOBS_P
    self.send_response(200)
    self.send_header("Content-Type","application/json")
    self.end_headers()
    self.wfile.write(json.dumps(LIST))
    print "TOTAL: "+str(len(JOBS_P))
    return

  def send_JOB(self):
    global JOBS_P
    global cert
    global key
    global IPDOCKER
    print "send_JOB"
    global timer
    if len(JOBS_P) > 0:
      JOB = JOBS_P.pop()
      r = requests.post("https://"+IPDOCKER+CRETEPATH, json=json.loads(JOB["Data"]), cert=(cert,key), verify=False)
      t = threading.Timer(30.0, self.send_JOB)
      t.daemon = True
      t.start()
    else:
      timer = False
    return

  def list_CONTAINERS(self):
    global JOBS_P
    global cert
    global key
    global IPDOCKER

    r = requests.get("https://"+IPDOCKER+"/v1.24/containers/json?all=0", cert=(cert,key), verify=False, headers=self.headers)
    return json.loads(r.content)

  def list_NODES(self):
    global JOBS_P
    global cert
    global key
    global IPDOCKER
    NODES = {}
    data = self.list_CONTAINERS()
    for cont in data:
        r = requests.get("https://"+IPDOCKER+"/v1.24/containers/"+cont["Id"]+"/stats?stream=0", cert=(cert,key), verify=False, headers=self.headers)
        data = json.loads(r.content)
        node = cont["Names"][0].split("/")[1]
        if node not in NODES:
            NODES[node] = {}
            NODES[node]['Containers'] = 0
            NODES[node]['CPU'] = 0
            NODES[node]['RAM'] = 0
        NODES[node]['Containers'] += 1
        NODES[node]['CPU'] += (float(data["cpu_stats"]["cpu_usage"]["total_usage"]) / float(data["cpu_stats"]["system_cpu_usage"]))*float(100)
        NODES[node]['RAM'] += (float(data["memory_stats"]["usage"]) / float(data["memory_stats"]["limit"]))*float(100)
    self.send_response(200)
    self.send_header("Content-Type","application/json")
    self.end_headers()
    self.wfile.write(json.dumps(NODES))
    return

  def do_GET(self):
    print  self.path
    global cert
    global key
    global IPDOCKER
    global REQUEST
    REQUEST += 1
    if "jobs/num" in self.path:
      self.num_JOBS()
    elif "jobs/list" in self.path:
      self.list_JOBS()
    elif "nodes/list" in self.path:
      self.list_NODES()
    else:
      print "do_GET "+str(REQUEST)
      r = requests.get("https://"+IPDOCKER+self.path, cert=(cert,key), verify=False, headers=self.headers)
      self.send_response(r.status_code)
      for header in r.headers:
        self.send_header(header,r.headers[header])
      self.end_headers()
      self.wfile.write(r.content)
    return

  def do_POST(self):
    global cert
    global key
    global IPDOCKER
    global JOBS_P
    global REQUEST
    REQUEST += 1
    print "do_POST "+str(REQUEST)
    if "containers/create" not in self.path and FAKE_ID_CONTAINER not in self.path and "//" not in self.path:
    #   self.headers[header]=self.client_address[0]+":"+str(self.client_address[1])
      if self.headers["content-length"] and int(self.headers["content-length"]) > 0:
        self.data = json.loads(self.rfile.readline().strip())
        r = requests.post("https://"+IPDOCKER+self.path, json=self.data, cert=(cert,key), verify=False)
      else:
        r = requests.post("https://"+IPDOCKER+self.path, data="", cert=(cert,key), verify=False)
      self.send_response(r.status_code)
      for header in r.headers:
        if header != "host":
          self.send_header(header,r.headers[header])
        else:
          self.send_header('host', self.client_address[0]+":"+self.client_address[1])
      self.end_headers()
      self.wfile.write(r.content)
    else:
      if "containers/create" in self.path:
        self.add_JOB()

      if FAKE_ID_CONTAINER in self.path or "//" in self.path:
        self.send_response(204)
        self.end_headers()
        msg = ''
      else:
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.end_headers()
        msg = "{\"Id\":\""+FAKE_ID_CONTAINER+"\",\"Warnings\":null}"
      self.wfile.write(msg)
    return

  def do_DELETE(self):
    global cert
    global key
    global IPDOCKER
    global REQUEST
    REQUEST += 1
    print "do_DELETE "+str(REQUEST)

    r = requests.delete("https://"+IPDOCKER+self.path, cert=(cert,key), verify=False, headers=self.headers)
    self.send_response(r.status_code)
    for header in r.headers:
      self.send_header(header,r.headers[header])
    self.end_headers()
    self.wfile.write(r.content)
    return

  def do_HEAD(self):
    global cert
    global key
    global IPDOCKER
    global REQUEST
    REQUEST += 1
    print "do_HEAD "+str(REQUEST)

    r = requests.head("https://"+IPDOCKER+self.path,  cert=(cert,key), verify=False, headers=self.headers)
    self.send_response(r.status_code)
    for header in r.headers:
      self.send_header(header,r.headers[header])
    self.end_headers()
    self.wfile.write(r.content)
    return

try:
  server = HTTPServer(('', PORT_NUMBER), myHandler)
  print 'Started httpserver on port ' , PORT_NUMBER
  server.serve_forever()

except KeyboardInterrupt:
  print '^C received, shutting down the web server'
  server.socket.close()
