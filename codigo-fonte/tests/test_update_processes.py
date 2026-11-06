import unittest
from update_service import own_mcp_processes

class UpdateProcessTests(unittest.TestCase):
 def test_only_same_installation_mcp_can_be_closed(self):
  rows=[{'ProcessId':1,'ExecutablePath':r'C:\Apps\PecaStudio.exe','CommandLine':r'"C:\Apps\PecaStudio.exe" --mcp --workspace "x"'},
        {'ProcessId':2,'ExecutablePath':r'C:\Apps\PecaStudio.exe','CommandLine':r'"C:\Apps\PecaStudio.exe"'},
        {'ProcessId':3,'ExecutablePath':r'D:\Other\PecaStudio.exe','CommandLine':'PecaStudio.exe --mcp'},
        {'ProcessId':4,'ExecutablePath':r'C:\Apps\python.exe','CommandLine':'python.exe --mcp'},
        {'ProcessId':5,'ExecutablePath':r'C:\Apps\PecaStudio.exe','CommandLine':'PecaStudio.exe --mcp-something'}]
  self.assertEqual(own_mcp_processes(rows,r'c:/apps/PecaStudio.exe',99),[1])
  self.assertEqual(own_mcp_processes(rows,r'C:\Apps\PecaStudio.exe',1),[])

if __name__=='__main__':unittest.main()
