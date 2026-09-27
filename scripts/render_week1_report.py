"""Render the source Markdown report to an offline, locally verified PDF."""
from html import escape
from pathlib import Path

from playwright.sync_api import sync_playwright

if __name__ == '__main__':
    source = Path('baocao/tuan1_tra_loi_cau_hoi.md')
    blocks = []
    for paragraph in source.read_text(encoding='utf-8').split('\n\n'):
        if paragraph.startswith('# '):
            blocks.append('<h1>' + escape(paragraph[2:]) + '</h1>')
        elif paragraph.startswith('## '):
            blocks.append('<h2>' + escape(paragraph[3:]) + '</h2>')
        else:
            css_class = ' class="reference"' if 'https://' in paragraph else ''
            blocks.append('<p' + css_class + '>' + escape(paragraph.replace('\n', ' ')) + '</p>')
    html = '<!doctype html><html lang="vi"><meta charset="utf-8"><style>' + (
        '@page {size:A4;margin:20mm 22mm 22mm} body{font:11pt/1.55 "Segoe UI",sans-serif;color:#111}'
        'h1{font-size:21pt;line-height:1.25;margin:0 0 20pt}h2{font-size:14pt;break-after:avoid;margin:20pt 0 7pt}'
        'p{margin:0 0 9pt;orphans:3;widows:3;overflow-wrap:anywhere}'
        'p.reference{font-size:9pt;line-height:1.3;margin-bottom:6pt}'
    ) + '</style><body>' + ''.join(blocks) + '</body></html>'
    source.with_suffix('.html').write_text(html, encoding='utf-8')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(source.with_suffix('.html').resolve().as_uri())
        page.pdf(path=str(source.with_suffix('.pdf')), format='A4', print_background=True,
                 display_header_footer=True, header_template='<span></span>',
                 footer_template='<div style="font:9px Arial;width:100%;text-align:center">'
                                 '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')
        browser.close()
    import fitz
    qa = Path('outputs/report_qa')
    qa.mkdir(parents=True, exist_ok=True)
    with fitz.open(source.with_suffix('.pdf')) as document:
        for index, page in enumerate(document):
            page.get_pixmap(matrix=fitz.Matrix(1, 1)).save(qa / f'week1_page_{index + 1}.png')
        print(f'PDF rendered: {len(document)} pages')
