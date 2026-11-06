import tempfile,unittest
from workspace_service import StudioService

SOURCE='<section data-export-frame data-width="300" data-height="400"><style>h1{font-size:var(--size,32px)}</style><h1 data-editable="title">Oferta</h1><span data-adjust="--size" data-min="10" data-max="80">Fonte</span></section>'
class HTMLWorkspaceTests(unittest.TestCase):
 def test_mcp_html_create_inspect_edit_and_collection_queue(self):
  with tempfile.TemporaryDirectory() as root:
   s=StudioService(root);p=s.dispatch('projects_create',{'name':'HTML','expectedRevision':0})['result']
   created=s.dispatch('pieces_create_html',{'projectId':p['id'],'title':'Arte','html':SOURCE,'expectedRevision':1});piece=created['result']
   self.assertEqual(s.dispatch('pieces_get_html',{'pieceId':piece['id']})['result']['html'],piece['htmlDocument']['html'])
   self.assertEqual(s.dispatch('pieces_list_editables',{'pieceId':piece['id']})['result']['editables'][0]['key'],'title')
   changed=s.dispatch('pieces_update_html',{'pieceId':piece['id'],'texts':{'title':'Nova oferta'},'controls':{'--size':48},'expectedRevision':2})
   self.assertIn('Nova oferta',changed['result']['htmlDocument']['html'])
   queued=s.dispatch('collections_export',{'projectId':p['id'],'format':'png','expectedRevision':3})
   self.assertEqual(len(queued['result']),1)
   self.assertEqual(queued['result'][0]['piece']['htmlDocument']['editables'][0]['value'],'Nova oferta')

if __name__=='__main__':unittest.main()
