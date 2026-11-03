"""Локальное приложение подсчёта людей и экспорта журнала обработок."""
from pathlib import Path
from datetime import datetime
from io import BytesIO
from contextlib import closing
import os, sqlite3, uuid
from flask import Flask, request, jsonify, render_template, send_file, url_for
from PIL import Image, UnidentifiedImageError
from reports import make_pdf, make_xlsx

BASE = Path(__file__).resolve().parent

def create_app(data_dir=None, detector=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
    data = Path(data_dir or os.environ.get('VISITOR_DATA_DIR', BASE/'data'))
    data.mkdir(parents=True, exist_ok=True)
    results = data/'results'
    results.mkdir(exist_ok=True)
    database = data/'history.db'
    with closing(sqlite3.connect(database)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS requests (
          id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
          original_filename TEXT NOT NULL, visitor_count INTEGER NOT NULL,
          result_filename TEXT NOT NULL)""")
        db.commit()
    active_detector = detector

    def history_rows():
        clauses, values = [], []
        dates = {}
        for key, operator in [('start','>='),('end','<=')]:
            value = request.args.get(key,'')
            if value:
                try:
                    datetime.strptime(value,'%Y-%m-%d')
                    if len(value)!=10: raise ValueError()
                except ValueError:
                    raise ValueError('Дата должна иметь формат ГГГГ-ММ-ДД.')
                dates[key]=value
                clauses.append('substr(created_at,1,10) '+operator+' ?')
                values.append(value)
        if dates.get('start','') > dates.get('end','9999'):
            raise ValueError('Начальная дата позже конечной.')
        sql='SELECT id,created_at,original_filename,visitor_count,result_filename FROM requests'
        if clauses: sql+=' WHERE '+' AND '.join(clauses)
        with closing(sqlite3.connect(database)) as db:
            return db.execute(sql+' ORDER BY id DESC',values).fetchall()

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(error='Размер файла превышает 8 МиБ.'),413

    @app.get('/')
    def index(): return render_template('index.html')

    @app.post('/process')
    def process_image():
        nonlocal active_detector
        file=request.files.get('image')
        if not file or not file.filename:
            return jsonify(error='Выберите изображение.'),400
        raw=file.read()
        try:
            with Image.open(BytesIO(raw)) as im:
                if im.width*im.height > 20_000_000:
                    return jsonify(error='Изображение должно содержать не более 20 млн пикселей.'),400
                im.verify()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            return jsonify(error='Не удалось прочитать изображение.'),400
        if active_detector is None:
            from detector import YoloDetector
            active_detector=YoloDetector(os.environ.get('YOLO_MODEL',str(BASE/'yolov8n.pt')))
        try:
            count, annotated = active_detector(raw)
        except Exception:
            app.logger.exception('Ошибка обработки изображения')
            return jsonify(error='Ошибка модели. Проверьте окружение и файл yolov8n.pt.'),500
        filename=uuid.uuid4().hex+'.jpg'
        path=results/filename
        path.write_bytes(annotated)
        original=Path(file.filename.replace('\\','/')).name[:200]
        try:
            with closing(sqlite3.connect(database)) as db:
                with db:
                    db.execute('INSERT INTO requests (created_at,original_filename,visitor_count,result_filename) VALUES (?,?,?,?)',
                      (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),original,int(count),filename))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return jsonify(count=int(count),result_url=url_for('result_image',filename=filename))

    @app.get('/results/<filename>')
    def result_image(filename):
        from flask import send_from_directory
        return send_from_directory(results,filename)

    @app.get('/history')
    def history():
        try: rows=history_rows()
        except ValueError as error: return str(error),400
        return render_template('history.html',rows=rows,start=request.args.get('start',''),end=request.args.get('end',''))

    @app.get('/reports/<format>')
    def export_report(format):
        if format not in ('pdf','xlsx'): return jsonify(error='Формат не поддерживается.'),404
        try: rows=history_rows()
        except ValueError as error: return jsonify(error=str(error)),400
        period='С '+(request.args.get('start') or 'начала журнала')+' по '+(request.args.get('end') or 'последнюю запись')
        content=make_pdf(rows,period) if format=='pdf' else make_xlsx(rows,period)
        mime='application/pdf' if format=='pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return send_file(BytesIO(content),mimetype=mime,as_attachment=True,download_name='processing-history.'+format)
    return app

if __name__=='__main__':
    create_app().run(host='127.0.0.1',port=int(os.environ.get('PORT','5000')),debug=False)
