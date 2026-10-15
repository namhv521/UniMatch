"""Export a locally reviewed Word thesis to Markdown and embedded figures."""
from pathlib import Path
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn

root=Path(__file__).resolve().parents[1]
doc=Document(root/'baocao/exports/11236160_HoangVanNam_KhoaLuan_UniMatch_hoan_thien.docx')
lines=[];in_toc=False;image_index=0
figures=root/'baocao/figures';figures.mkdir(exist_ok=True)
for element in doc.element.body:
 if element.tag==qn('w:p'):
  p=Paragraph(element,doc);text=p.text.strip()
  if text=='MỤC LỤC':
   in_toc=True;lines.extend(['# MỤC LỤC','', 'Mục lục tự động có trong bản Word và PDF.','']);continue
  if text=='LỜI CAM ĐOAN':in_toc=False
  if in_toc:continue
  if text:
   level=int(p.style.name[-1]) if p.style.name.startswith('Heading ') and p.style.name[-1].isdigit() else 0
   lines.extend([('#'*level+' ' if level else '')+text,''])
  for drawing in p._p.findall('.//'+qn('a:blip')):
   rid=drawing.get(qn('r:embed'))
   if rid:
    part=doc.part.related_parts[rid];image_index+=1;ext=part.partname.split('.')[-1];name=f'report-figure-{image_index:02}.{ext}'
    (figures/name).write_bytes(part.blob);lines.extend([f'![Hình minh họa trong báo cáo](figures/{name})',''])
 elif element.tag==qn('w:tbl'):
  t=Table(element,doc);rows=[[c.text.replace('\n',' ').replace('|','/') for c in row.cells] for row in t.rows]
  if rows:
   lines.append('| '+' | '.join(rows[0])+' |');lines.append('| '+' | '.join(['---']*len(rows[0]))+' |')
   lines.extend('| '+' | '.join(row)+' |' for row in rows[1:]);lines.append('')
(root/'baocao/khoa_luan_20261016.md').write_text('\n'.join(lines),encoding='utf-8')
print('Markdown exported; figures:',image_index)
