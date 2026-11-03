"""PDF и XLSX формируются из одной выборки SQLite."""
from io import BytesIO
from pathlib import Path
import os
from xml.sax.saxutils import escape
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HEADERS=['№','Дата и время','Исходный файл','Людей на снимке']
NOTE='Сумма по снимкам не является числом уникальных посетителей.'

def make_xlsx(rows,period):
    wb=Workbook(); ws=wb.active; ws.title='Обработки'
    ws.append(['Журнал обработки изображений']); ws.append([period]); ws.append([NOTE]); ws.append(HEADERS)
    for row in rows:
        ws.append(list(row[:4]))
        # Имя загруженного файла сохраняется текстом, даже если начинается с =.
        ws.cell(ws.max_row,3).data_type='s'
    last=ws.max_row
    ws.append(['Количество обработок',len(rows)])
    ws.append(['Сумма обнаружений по снимкам',sum(r[3] for r in rows)])
    for cell in ws[4]:
        cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='244D6A')
    for col,width in [('A',34),('B',23),('C',55),('D',22)]: ws.column_dimensions[col].width=width
    for row in ws.iter_rows():
        for cell in row: cell.alignment=Alignment(vertical='top',wrap_text=True)
    ws.freeze_panes='A5';ws.auto_filter.ref=f'A4:D{max(4,last)}'
    ws.print_title_rows='1:4'; ws.sheet_properties.pageSetUpPr.fitToPage=True
    ws.page_setup.orientation='landscape';ws.page_setup.paperSize=ws.PAPERSIZE_A4;ws.page_setup.fitToWidth=1;ws.page_setup.fitToHeight=0
    stream=BytesIO();wb.save(stream);return stream.getvalue()

def make_pdf(rows,period):
    candidates=[os.environ.get('REPORT_FONT',''),r'C:\Windows\Fonts\arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/Library/Fonts/Arial.ttf']
    font=next((p for p in candidates if p and Path(p).is_file()),None)
    if not font: raise RuntimeError('Укажите путь к Unicode-шрифту в REPORT_FONT.')
    if 'ReportFont' not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(TTFont('ReportFont',font))
    style=ParagraphStyle('body',fontName='ReportFont',fontSize=9,leading=12)
    title=ParagraphStyle('title',parent=style,fontSize=16,leading=20,spaceAfter=10)
    def p(value): return Paragraph(escape(str(value)),style)
    stream=BytesIO()
    doc=SimpleDocTemplate(stream,pagesize=landscape(A4),leftMargin=30,rightMargin=30,topMargin=30,bottomMargin=35)
    story=[Paragraph('Журнал обработки изображений',title),p(period),Spacer(1,8),p(NOTE),Spacer(1,12)]
    data=[[p(h) for h in HEADERS]]+[[p(v) for v in row[:4]] for row in rows]
    if not rows:data.append([p(''),p(''),p('Нет записей за выбранный период'),p('')])
    table=Table(data,colWidths=[35,125,480,140],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DDE8F0')),('GRID',(0,0),(-1,-1),.4,colors.grey),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story += [table,Spacer(1,12),p(f'Количество обработок: {len(rows)}. Сумма обнаружений по снимкам: {sum(r[3] for r in rows)}.')]
    def footer(canvas,document):
        canvas.setFont('ReportFont',9);canvas.drawRightString(810,18,f'Страница {document.page}')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()
