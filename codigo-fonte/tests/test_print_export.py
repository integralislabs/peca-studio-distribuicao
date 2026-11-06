import unittest,importlib.util,io,re,base64,subprocess,tempfile
from pathlib import Path
SPEC=importlib.util.find_spec('print_service')
if SPEC:
    from print_service import export_pdf,PrintError

def piece():
    return {'title':'Impressão de teste','slides':[{'width':1080,'height':1350,'bg':'#ffffff','layers':[{'id':'text','type':'text','visible':True,'name':'Título','text':'Oferta R$ 29,90','x':70,'y':90,'w':900,'font':'Arial','size':64,'color':'#112233','bold':True,'italic':False,'underline':False,'align':'left','lineHeight':1.15,'letterSpacing':0}]}]}

class PrintTests(unittest.TestCase):
    def test_00_exporter_available(self):self.assertIsNotNone(SPEC,'PDF exporter missing')
    @unittest.skipUnless(SPEC,'exporter not implemented')
    def test_art_physical_size_and_vector_text(self):
        result=export_pdf({'piece':piece(),'options':{'dpi':300,'paper':'art'}})
        data=base64.b64decode(result['base64']);self.assertTrue(data.startswith(b'%PDF-'))
        with tempfile.TemporaryDirectory() as root:
            pdf=Path(root)/'print.pdf';pdf.write_bytes(data)
            info=subprocess.check_output(['pdfinfo',str(pdf)]).decode('utf-8',errors='replace');self.assertIn('259.2',info)
            text=subprocess.check_output(['pdftotext',str(pdf),'-']).decode('utf-8');self.assertIn('29,90',text)
        self.assertEqual(result['pages'],1);self.assertTrue(result['vectorText'])
    @unittest.skipUnless(SPEC,'exporter not implemented')
    def test_multiple_pages_bleed_crop_and_a4(self):
        p=piece();p['slides']*=3
        art=export_pdf({'piece':p,'options':{'paper':'art','dpi':300,'bleedMm':3,'cropMarks':True}})
        self.assertEqual(art['pages'],3);self.assertGreater(art['pageSizes'][0][0],259.2+17)
        a4=export_pdf({'piece':piece(),'options':{'paper':'a4','dpi':300}})
        self.assertAlmostEqual(a4['pageSizes'][0][0],595.2756,places=2)
    @unittest.skipUnless(SPEC,'exporter not implemented')
    def test_invalid_options_and_external_images_rejected(self):
        for options in [{'dpi':0},{'dpi':float('nan')},{'paper':'custom','paperWidthMm':0,'paperHeightMm':20},{'paper':'a4','cropMarks':True}]:
            with self.assertRaises(PrintError):export_pdf({'piece':piece(),'options':options})
        p=piece();p['slides'][0]['bgImage']='https://example.com/a.png'
        with self.assertRaises(PrintError):export_pdf({'piece':p})

if __name__=='__main__':unittest.main()
