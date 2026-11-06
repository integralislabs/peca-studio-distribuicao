import concurrent.futures
import tempfile
import unittest
from pathlib import Path
from workspace_service import WorkspaceStore, StudioService, ConflictError

class WorkspaceTests(unittest.TestCase):
    def test_atomic_conflict_idempotence_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            s=WorkspaceStore(d); data={'version':1,'projects':[],'pieces':[]}
            self.assertEqual(s.read()['revision'],0)
            first=s.write(data,0,'one')
            self.assertEqual(first,s.write(data,0,'one'))
            with self.assertRaises(ConflictError): s.write(data,0)
            with self.assertRaises(ConflictError): s.write({**data,'projects':[{'id':'x'}]},1,'one')
            s.write(data,1)
            self.assertTrue(list((Path(d)/'backups').glob('*.json')))
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                def write(_):
                    try: WorkspaceStore(d).write(data,2); return True
                    except ConflictError: return False
                self.assertEqual(sum(pool.map(write,range(2))),1)
    def test_tools_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            s=StudioService(d)
            p=s.dispatch('projects_create',{'name':'Teste','expectedRevision':0,'operationId':'p'})
            pid=p['result']['id']
            a={'projectId':pid,'title':'Arte','expectedRevision':1,'operationId':'piece'}
            piece=s.dispatch('pieces_create',a)
            self.assertEqual(piece,s.dispatch('pieces_create',a))
            item=piece['result']; slide=item['slides'][0]; layer=slide['layers'][0]
            r=s.dispatch('pieces_update_texts',{'pieceId':item['id'],'texts':{layer['id']:'Novo'},'expectedRevision':2})
            self.assertEqual(r['result']['slides'][0]['layers'][0]['text'],'Novo')
            self.assertEqual(s.dispatch('pieces_get',{'pieceId':item['id']})['revision'],3)
            e=s.dispatch('pieces_export',{'pieceId':item['id'],'format':'png','expectedRevision':3})
            self.assertEqual(e['result']['status'],'pending')
    def test_reject_invalid_state_and_path(self):
        with tempfile.TemporaryDirectory() as d:
            s=WorkspaceStore(d)
            with self.assertRaises(ValueError): s.write({'version':1,'projects':[],'pieces':[{}]},0)
            with self.assertRaises(ValueError): s.asset_path('../secret')


class ExportTests(unittest.TestCase):
    def test_export_completion_restart_and_asset_containment(self):
        import base64
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            s=StudioService(d)
            p=s.dispatch('projects_create',{'name':'A','expectedRevision':0})['result']
            p=s.dispatch('pieces_create',{'projectId':p['id'],'expectedRevision':1})['result']
            args={'pieceId':p['id'],'expectedRevision':2,'operationId':'export','format':'png'}
            job=s.dispatch('pieces_export',args)['result']
            self.assertEqual(s.pending_exports()[0]['piece']['id'],p['id'])
            payload={'base64':base64.b64encode(b'\x89PNG\r\n\x1a\nfixture').decode(),'mime':'image/png'}
            done=s.complete_export(job['id'],payload)
            self.assertEqual(s.pending_exports(),[])
            self.assertEqual(done,StudioService(d).complete_export(job['id'],payload))
            self.assertEqual(s.dispatch('pieces_export',args)['result']['id'],job['id'])
            before=s.store.read()
            with patch('workspace_service.os.replace',side_effect=OSError('disk')):
                with self.assertRaises(OSError): s.store.write(before['data'],before['revision'])
            self.assertEqual(s.store.read(),before)

class ImageTests(unittest.TestCase):
    def test_image_tool_adds_image_layer(self):
        import base64
        with tempfile.TemporaryDirectory() as d:
            s=StudioService(d)
            project=s.dispatch('projects_create',{'name':'A','expectedRevision':0})['result']
            piece=s.dispatch('pieces_create',{'projectId':project['id'],'expectedRevision':1})['result']
            src='data:image/png;base64,'+base64.b64encode(b'fixture').decode()
            result=s.dispatch('pieces_set_image',{'pieceId':piece['id'],'slideId':piece['slides'][0]['id'],'image':src,'expectedRevision':2})
            self.assertEqual(result['result']['slides'][0]['layers'][-1]['src'],src)


class RegressionTests(unittest.TestCase):
    def test_validation_optional_styles_fonts_and_metadata(self):
        import copy
        from workspace_service import validate_state
        with tempfile.TemporaryDirectory() as d:
            s=StudioService(d); project=s.dispatch('projects_create',{'name':'A','expectedRevision':0})['result']
            s.dispatch('pieces_create',{'projectId':project['id'],'expectedRevision':1})
            state=s.store.read()['data']
            for key,value in [('font','Not installed'),('radius',-1),('opacity',2)]:
                invalid=copy.deepcopy(state); invalid['pieces'][0]['slides'][0]['layers'][0][key]=value
                with self.assertRaises(ValueError,msg=key): validate_state(invalid)
            for key,value in [('caption','x'*4001),('contentKind','invalid'),('fonts',[{'name':'Bad','data':'invalid'}])]:
                invalid=copy.deepcopy(state); invalid['pieces'][0][key]=value
                with self.assertRaises(ValueError,msg=key): validate_state(invalid)
    def test_receipts_retention_and_changed_snapshots(self):
        import json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            s=StudioService(d); project=s.dispatch('projects_create',{'name':'A','expectedRevision':0})['result']
            s.dispatch('pieces_create',{'projectId':project['id'],'expectedRevision':1})
            store=s.store; state=store.read()['data']
            with patch.object(store,'_atomic',wraps=store._atomic) as atomic:
                store.write(state,2,'same')
                self.assertFalse(any('/pieces/' in str(c.args[0]).replace('\\','/') for c in atomic.call_args_list))
            for i in range(24): store.write(state,3+i,'save-'+str(i))
            raw=json.loads(store.path.read_text('utf-8'))
            self.assertNotIn('data',raw['_receipts']['save-23'].get('response',{}))
            self.assertLessEqual(len(list((Path(d)/'backups').glob('*.json'))),20)
            self.assertLess(len(json.dumps(raw['_receipts'])),20000)

class ReceiptWindowTests(unittest.TestCase):
    def test_window_expires_without_reexecution(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            store=WorkspaceStore(d); state=store.read()['data']
            store.write(state,0,'old')
            # Seed retained compact receipts, then perform the eviction through production write.
            raw=json.loads(store.path.read_text('utf-8'))
            for i in range(511): raw['_receipts']['seed-'+str(i)]={'revision':1,'fingerprint':'fixture'}
            raw['_receiptOrder']=list(raw['_receipts'])
            store.path.write_text(json.dumps(raw),encoding='utf-8')
            store.write(state,1,'new')
            raw=json.loads(store.path.read_text('utf-8'))
            self.assertEqual(len(raw['_receipts']),512)
            self.assertEqual(len(raw['_expiredOperations']),1)
            with self.assertRaises(ConflictError): store.write(state,2,'old')
            self.assertEqual(store.read()['revision'],2)
    def test_dispatch_retry_uses_current_revision(self):
        with tempfile.TemporaryDirectory() as d:
            s=StudioService(d)
            args={'name':'A','expectedRevision':0,'operationId':'create'}
            first=s.dispatch('projects_create',args)
            state=s.store.read()['data']; state['projects'][0]['name']='Edited'
            s.store.write(state,1)
            retry=s.dispatch('projects_create',args)
            self.assertEqual(retry['revision'],2)
            self.assertEqual(retry['result']['name'],'Edited')
            self.assertEqual(retry['result']['id'],first['result']['id'])


class CompositionTests(unittest.TestCase):
    def test_import_replace_portable_composition_and_idempotence(self):
        import copy
        import base64
        with tempfile.TemporaryDirectory() as d:
            service=StudioService(d)
            project=service.dispatch('projects_create',{'name':'Destino','expectedRevision':0})['result']
            original=service.dispatch('pieces_create',{'projectId':project['id'],'expectedRevision':1})['result']
            composition=copy.deepcopy(original)
            first=composition['slides'][0]['layers'][0]
            composition['slides'][0]['layers']=[{**first,'id':'foreign-'+str(i),'text':'Texto '+str(i)} for i in range(3)]
            composition['fonts']=[{'name':'Portable','data':'data:font/ttf;base64,'+base64.b64encode(b'\x00\x01\x00\x00'+b'\x00'*12).decode()}]
            composition['slides'][0]['layers'][0]['font']='Portable'
            composition['qa']={'approved':False,'referenceHash':'fixture'}
            args={'projectId':project['id'],'piece':composition,'expectedRevision':2,'operationId':'import'}
            imported=service.dispatch('studio_pieces_import',args)
            self.assertNotEqual(imported['result']['id'],original['id'])
            self.assertNotEqual(imported['result']['slides'][0]['id'],original['slides'][0]['id'])
            self.assertEqual(len(imported['result']['slides'][0]['layers']),3)
            self.assertEqual(imported['result']['fonts'],composition['fonts'])
            self.assertEqual(imported['result']['qa'],composition['qa'])
            self.assertEqual(service.dispatch('pieces_import',args),imported)
            replacement=copy.deepcopy(imported['result']); replacement['slides'][0]['layers'][1]['text']='Editado'
            replace_args={'pieceId':imported['result']['id'],'piece':replacement,'expectedRevision':3,'operationId':'replace'}
            updated=service.dispatch('pieces_replace',replace_args)
            self.assertEqual(updated['result']['id'],imported['result']['id'])
            self.assertEqual(updated['result']['slides'][0]['layers'][1]['text'],'Editado')
            self.assertEqual(service.dispatch('pieces_replace',replace_args),updated)
            self.assertEqual(len(service.dispatch('pieces_list',{})['result']),2)
            with self.assertRaises(ConflictError): service.dispatch('pieces_replace',{**replace_args,'operationId':'other','expectedRevision':3})
            invalid=copy.deepcopy(replacement); invalid['slides'][0]['layers'][0]['font']='Missing'
            with self.assertRaises(ValueError): service.dispatch('pieces_replace',{'pieceId':imported['result']['id'],'piece':invalid,'expectedRevision':4})
            self.assertEqual(service.store.read()['revision'],4)

if __name__=='__main__': unittest.main()
