import base64
import io
import unittest
import time
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from image_conversion import capabilities, analyze_image, convert_image


class ImageConversionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        im = Image.new('RGB', (800, 300), 'white')
        ImageDraw.Draw(im).text((50, 80), 'Oferta R$ 49,90', font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 52), fill='black')
        out = io.BytesIO(); im.save(out, 'PNG')
        cls.image = 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode()

    def test_real_ocr_and_reviewed_conversion(self):
        self.assertTrue(capabilities()['ocr'])
        analysis = analyze_image({'image': self.image, 'language': 'por+eng'})
        self.assertEqual((analysis['width'], analysis['height']), (800, 300))
        self.assertIn('49,90', ' '.join(b['text'] for b in analysis['blocks']))
        blocks = analysis['blocks']; blocks[0]['text'] = 'Preço revisado'; blocks[0]['selected'] = True
        result = convert_image({'image': self.image, 'blocks': blocks})
        self.assertEqual(result['reference']['image'], self.image)
        self.assertEqual(result['slide']['layers'][0]['text'], 'Preço revisado')
        self.assertEqual(result['slide']['layers'][0]['font'], 'Arial')
        self.assertEqual(result['report']['qa']['status'], 'pending')
        self.assertEqual(len(result['report']['referenceHash']), 64)

    def test_invalid_image_and_blocks_rejected(self):
        for image in ['https://example.com/a.png', 'data:image/svg+xml;base64,AAAA', 'data:image/png;base64,AAAA']:
            with self.assertRaises(ValueError): analyze_image({'image': image})
        with self.assertRaises(ValueError):
            convert_image({'image': self.image, 'blocks': [{'text': 'x', 'x': -1, 'y': 0, 'w': 10, 'h': 10}]})

    def test_unselected_remains_in_background(self):
        result = convert_image({'image': self.image, 'blocks': [{'id': 'b1', 'text': 'Oferta', 'x': 50, 'y': 80, 'w': 170, 'h': 60, 'selected': False}]})
        self.assertEqual(result['slide']['layers'], [])
        self.assertEqual(result['report']['blocks'], [])

    def test_101_selected_blocks_rejected_and_100_fit_layer_budget(self):
        blocks = [{'id': str(i), 'text': 'Linha', 'x': (i % 20)*35, 'y': (i // 20)*40,
                   'w': 30, 'h': 20, 'selected': True} for i in range(101)]
        with self.assertRaisesRegex(ValueError, '100'):
            convert_image({'image': self.image, 'blocks': blocks})
        blocks[-1]['selected'] = False
        result = convert_image({'image': self.image, 'blocks': blocks})
        self.assertEqual(len(result['slide']['layers']), 100)
        self.assertTrue(result['slide']['bgImage'])
        self.assertLessEqual(len(result['slide']['layers']), 100)
        state = {'version': 1, 'projects': [{'id': 'qa-project', 'name': 'QA', 'color': '#123456', 'folders': []}],
                 'pieces': [{'id': 'qa-piece', 'projectId': 'qa-project', 'folderId': None, 'title': '100 blocos',
                             'channel': 'Instagram', 'format': 'feed', 'status': 'Rascunho', 'slides': [result['slide']]}]}
        checked = subprocess.run(['node', '--input-type=module', '-e',
                                  "import {validateState} from './model.js';let s='';for await(const c of process.stdin)s+=c;validateState(JSON.parse(s));"],
                                 input=json.dumps(state), text=True, capture_output=True, cwd=Path(__file__).resolve().parents[1], timeout=30)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_scale_ten_conversions_100_blocks(self):
        blocks = [{'id': str(i), 'text': 'Linha', 'x': (i % 20)*35, 'y': (i // 20)*40,
                   'w': 30, 'h': 20, 'selected': True} for i in range(100)]
        started = time.perf_counter()
        for _ in range(10):
            result = convert_image({'image': self.image, 'blocks': blocks})
            self.assertEqual(len(result['slide']['layers']), 100)
        elapsed = time.perf_counter()-started
        print(f'\nESCALA: 10 conversões x 100 blocos: {elapsed:.3f}s total; {elapsed/10:.3f}s média (não mede OCR).')

if __name__ == '__main__': unittest.main()
