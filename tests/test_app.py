import unittest, tempfile, sqlite3
from pathlib import Path
from io import BytesIO
from PIL import Image
from openpyxl import load_workbook
from app import create_app

class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.data=Path(self.temp.name)
        self.app=create_app(self.data,lambda raw:(2,raw));self.app.testing=True
        self.client=self.app.test_client()
        im=BytesIO();Image.new('RGB',(32,32),'white').save(im,'JPEG');self.raw=im.getvalue()
    def tearDown(self):self.temp.cleanup()
    def upload(self,name='пример.jpg'):
        return self.client.post('/process',data={'image':(BytesIO(self.raw),name)})
    def test_01_pages(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertIn('Скачать PDF',self.client.get('/history').get_data(as_text=True))
    def test_02_process_and_history(self):
        r=self.upload();self.assertEqual(r.status_code,200);self.assertEqual(r.json['count'],2)
        with self.client.get(r.json['result_url']) as result:
            self.assertEqual(result.data,self.raw)
        self.assertIn('пример.jpg',self.client.get('/history').get_data(as_text=True))
    def test_03_missing_file(self):self.assertEqual(self.client.post('/process').status_code,400)
    def test_04_invalid_file(self):self.assertEqual(self.client.post('/process',data={'image':(BytesIO(b'bad'),'bad.jpg')}).status_code,400)
    def test_05_pdf(self):
        self.upload();r=self.client.get('/reports/pdf');self.assertEqual(r.status_code,200)
        self.assertTrue(r.data.startswith(b'%PDF'));self.assertIn('attachment',r.headers['Content-Disposition'])
    def test_06_excel_values(self):
        self.upload();r=self.client.get('/reports/xlsx');ws=load_workbook(BytesIO(r.data)).active
        self.assertEqual(ws['C5'].value,'пример.jpg');self.assertEqual(ws['D5'].value,2)
        self.assertEqual(ws['B6'].value,1);self.assertEqual(ws['B7'].value,2)
    def test_07_empty_exports(self):
        self.assertEqual(self.client.get('/reports/pdf').status_code,200)
        ws=load_workbook(BytesIO(self.client.get('/reports/xlsx').data)).active
        self.assertEqual(ws['B5'].value,0)
    def test_08_invalid_dates(self):
        for query in ['start=bad','start=2026-02-30','start=2026-11-04&end=2026-11-03']:
            self.assertEqual(self.client.get('/reports/pdf?'+query).status_code,400)
    def test_09_date_filter(self):
        self.upload()
        ws=load_workbook(BytesIO(self.client.get('/reports/xlsx?end=2000-01-01').data)).active
        self.assertEqual(ws['B5'].value,0)
        with sqlite3.connect(self.data/'history.db') as db: db.execute("UPDATE requests SET created_at='2026-11-03 12:00:00'")
        ws=load_workbook(BytesIO(self.client.get('/reports/xlsx?start=2026-11-03&end=2026-11-03').data)).active
        self.assertEqual(ws['C5'].value,'пример.jpg')
    def test_10_formula_filename(self):
        self.upload('=1+1.jpg');ws=load_workbook(BytesIO(self.client.get('/reports/xlsx').data)).active
        self.assertEqual(ws['C5'].data_type,'s')
    def test_11_unsupported_format(self):self.assertEqual(self.client.get('/reports/csv').status_code,404)
    def test_12_size_limit(self):self.assertEqual(self.client.post('/process',data={'image':(BytesIO(b'x'*9*1024*1024),'large.jpg')}).status_code,413)
    def test_13_persistence(self):
        self.upload();client=create_app(self.data,lambda raw:(2,raw)).test_client()
        self.assertIn('пример.jpg',client.get('/history').get_data(as_text=True))

if __name__=='__main__':unittest.main()
