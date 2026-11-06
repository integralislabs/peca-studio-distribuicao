import unittest
from http.server import BaseHTTPRequestHandler
from desktop_app import StrictHTTPServer
class ExclusivePort(unittest.TestCase):
 def test_second_bind_is_rejected(self):
  server=StrictHTTPServer(('127.0.0.1',0),BaseHTTPRequestHandler)
  try:
   with self.assertRaises(OSError):StrictHTTPServer(('127.0.0.1',server.server_port),BaseHTTPRequestHandler)
  finally:server.server_close()
