import os
import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
pdfs = [os.path.join(ROOT, f) for f in os.listdir(ROOT) if f.lower().endswith('.pdf')]
print('Found PDFs:', pdfs)
if not pdfs:
    print('No PDF files found in project root')
    exit(1)

files = []
opened = []
for p in pdfs:
    f = open(p, 'rb')
    opened.append(f)
    files.append(('file', (os.path.basename(p), f, 'application/pdf')))

try:
    with requests.Session() as s:
        resp = s.post('http://localhost:5000/upload', files=files, data={'pdf_optimizado': 'on', 'pdf_factura': 'on'}, timeout=30)
        print('Upload status:', resp.status_code)
        try:
            print('Upload response JSON:', resp.json())
        except Exception as e:
            print('Response text:', resp.text)

        # Consultar API de facturas
        resp2 = s.get('http://localhost:5000/api/facturas', timeout=10)
        print('API /api/facturas status:', resp2.status_code)
        try:
            print('Facturas:', resp2.json())
        except Exception as e:
            print('API response text:', resp2.text)
except Exception as e:
    print('Error during upload:', type(e), e)
    import traceback
    traceback.print_exc()
finally:
    for f in opened:
        try:
            f.close()
        except:
            pass
