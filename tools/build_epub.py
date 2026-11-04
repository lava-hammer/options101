#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 futures101/mds 下的 Markdown 一次性打包成 EPUB 3。"""
import os, re, zipfile, uuid, datetime, html
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MDS = os.path.join(ROOT, 'mds')
OUT = os.path.join(ROOT, '期权101-v1.epub')

# ---------- 章节顺序 ----------
order = []
for f in sorted(os.listdir(MDS)):
    if f.endswith('.md'):
        order.append(f)

def stem(f):
    return f[:4]

def xname(f):
    return f's{stem(f)}.xhtml'

# ---------- 行内 Markdown ----------
def esc(t):
    return (t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

def inline(t, fmap):
    t = esc(t)
    # 行内代码
    codes = []
    def keep_code(m):
        codes.append(m.group(1))
        return f'\x00{len(codes)-1}\x00'
    t = re.sub(r'`([^`]+)`', keep_code, t)
    # 粗体
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    # 链接（内部 md → xhtml；外部保留）
    def link(m):
        text, url = m.group(1), m.group(2)
        if url.startswith('http://') or url.startswith('https://'):
            return f'<a href="{esc(url)}">{text}</a>'
        base = os.path.basename(url.split('#')[0])
        if base in fmap:
            return f'<a href="{xname(base)}">{text}</a>'
        return text
    t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, t)
    # 还原行内代码
    def back(m):
        return f'<code>{esc(codes[int(m.group(1))])}</code>'
    t = re.sub('\x00(\\d+)\x00', back, t)
    return t

# ---------- 块级 Markdown ----------
def md_to_html(text, fmap):
    lines = text.split('\n')
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        # 代码块
        if s.startswith('```'):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith('```'):
                buf.append(lines[i]); i += 1
            i += 1
            out.append('<pre><code>' + esc('\n'.join(buf)) + '</code></pre>')
            continue
        # 标题
        m = re.match(r'^(#{1,4})\s+(.*)$', s)
        if m:
            lvl = len(m.group(1))
            out.append(f'<h{lvl}>{inline(m.group(2), fmap)}</h{lvl}>')
            i += 1
            continue
        # 水平线
        if re.match(r'^-{3,}$', s):
            out.append('<hr/>')
            i += 1
            continue
        # 表格
        if s.startswith('|') and i + 1 < n and re.match(r'^\|[\s:\-|]+\|$', lines[i+1].strip()):
            header = [c.strip() for c in s.strip('|').split('|')]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith('|'):
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            t = ['<table>', '<thead><tr>']
            for h in header:
                t.append(f'<th>{inline(h, fmap)}</th>')
            t.append('</tr></thead><tbody>')
            for r in rows:
                t.append('<tr>')
                for c in r:
                    t.append(f'<td>{inline(c, fmap)}</td>')
                t.append('</tr>')
            t.append('</tbody></table>')
            out.append(''.join(t))
            continue
        # 引用块（连续 > 行合并）
        if s.startswith('>'):
            buf = []
            while i < n and lines[i].strip().startswith('>'):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append('<blockquote><p>' + '<br/>'.join(inline(x, fmap) for x in buf if x) + '</p></blockquote>')
            continue
        # 无序列表
        if re.match(r'^[-*]\s+', s):
            items = []
            while i < n and re.match(r'^[-*]\s+', lines[i].strip()):
                items.append(re.sub(r'^[-*]\s+', '', lines[i].strip()))
                i += 1
            out.append('<ul>' + ''.join(f'<li>{inline(x, fmap)}</li>' for x in items) + '</ul>')
            continue
        # 有序列表
        if re.match(r'^\d+\.\s+', s):
            items = []
            while i < n and re.match(r'^\d+\.\s+', lines[i].strip()):
                items.append(re.sub(r'^\d+\.\s+', '', lines[i].strip()))
                i += 1
            out.append('<ol>' + ''.join(f'<li>{inline(x, fmap)}</li>' for x in items) + '</ol>')
            continue
        # 段落：连续普通行合并
        buf = []
        while i < n:
            cur = lines[i].strip()
            if not cur or cur.startswith(('#', '>', '|', '```', '-', '*')) or re.match(r'^\d+\.\s+', cur) or re.match(r'^-{3,}$', cur):
                break
            buf.append(cur)
            i += 1
        if buf:
            out.append('<p>' + inline(''.join(buf) if all('\u4e00' <= ch <= '\u9fff' or ch in '，。；：！？、（）「」' for ch in ''.join(buf)[:1]) else ''.join(buf), fmap) + '</p>')
        else:
            i += 1
    return '\n'.join(out)

# ---------- 读取章节 ----------
chapters = []
for f in order:
    p = os.path.join(MDS, f)
    text = open(p, encoding='utf-8').read()
    first = text.split('\n', 1)[0].strip()
    title = first[2:].strip() if first.startswith('# ') else f
    chapters.append({'file': f, 'title': title, 'text': text})

fmap = {c['file']: xname(c['file']) for c in chapters}

# ---------- 封面 ----------
cover = '''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN" lang="zh-CN">
<head><title>期权 101</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body class="cover-body">
<section class="cover" epub:type="cover">
<h1 class="cover-title">期权 101</h1>
<div class="cover-rule"></div>
<p class="cover-sub">从零开始到第一笔交易</p>
<p class="cover-author">作者：大马</p>
<p class="cover-date">2026/11/4</p>
</section>
</body>
</html>'''

# ---------- CSS ----------
css = '''@charset "utf-8";
html, body { margin: 0; padding: 0; }
body { font-family: "Songti SC", "Noto Serif CJK SC", "Source Han Serif SC", serif; line-height: 1.8; color: #1a1a1a; }
p { margin: 0.65em 0; text-indent: 2em; text-align: justify; }
h1, h2, h3, h4 { font-weight: bold; line-height: 1.4; page-break-after: avoid; }
h1 { font-size: 1.55em; margin: 0.4em 0 0.8em; }
h2 { font-size: 1.22em; margin: 1.5em 0 0.5em; }
h3 { font-size: 1.06em; margin: 1.2em 0 0.4em; }
blockquote { margin: 1em 0; padding: 0.6em 0.9em; border-left: 3px solid #8a7a5c; background: #f6f3ec; }
blockquote p { text-indent: 0; }
ul, ol { margin: 0.6em 0; padding-left: 1.6em; }
li { margin: 0.25em 0; }
table { width: 100%; border-collapse: collapse; margin: 1em 0; font-size: 0.88em; }
th, td { border: 1px solid #cdc5b4; padding: 5px 6px; text-align: left; vertical-align: top; }
th { background: #efe9dc; font-weight: bold; }
code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 0.9em; background: #f1ede3; padding: 0 2px; }
pre { background: #f1ede3; padding: 0.8em; overflow-x: auto; font-size: 0.85em; line-height: 1.5; }
hr { border: none; border-top: 1px solid #c9c1b0; margin: 1.4em 0; }

/* 封面 */
body.cover-body { background: #f6f1e7; }
.cover { margin: 0; padding: 26% 12% 0; color: #2a251e; text-align: center; }
.cover-title { font-size: 3.0em; letter-spacing: 0.08em; margin: 0; color: #1c1a17; }
.cover-rule { width: 4em; border-top: 2px solid #8a7a5c; margin: 1.4em auto; }
.cover-sub { font-size: 1.15em; color: #4e4639; text-indent: 0; margin: 0 0 3.2em; }
.cover-author { font-size: 0.95em; color: #5c5446; text-indent: 0; margin: 0.4em 0 0.2em; }
.cover-date { font-size: 0.85em; color: #8a8070; text-indent: 0; margin: 0.2em 0; }

/* 部分分隔页 */
.part-page { margin: 0; padding: 34% 10% 0; text-align: center; }
.part-kicker { font-size: 0.8em; letter-spacing: 0.3em; color: #8a7a5c; text-indent: 0; margin: 0 0 1em; }
.part-title { font-size: 2.1em; letter-spacing: 0.1em; margin: 0; }
.part-rule { width: 3em; border-top: 1px solid #b9a77f; margin: 1.2em auto; }
.part-sub { font-size: 1.05em; color: #6b6151; text-indent: 0; margin: 0; }
'''

# ---------- 生成章节 XHTML ----------
def page(title, body, cls='', epubtype='chapter'):
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN" lang="zh-CN">
<head><title>{esc(title)}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body{(' class="'+cls+'"') if cls else ''}>
<section epub:type="{epubtype}">
{body}
</section>
</body>
</html>'''

pages = {}
for c in chapters:
    f = c['file']
    text = c['text']
    if f.startswith('0001'):
        continue
    body = md_to_html(text, fmap)
    if re.match(r'^[1-5]000-', f):
        # 部分分隔页：解析部分名与副标题
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        part = lines[0].lstrip('# ').strip()
        sub = lines[1].lstrip('# ').strip() if len(lines) > 1 else ''
        body = f'''<div class="part-page">
<h1 class="part-title">{esc(part)}</h1>
<div class="part-rule"></div>
<p class="part-sub">{esc(sub)}</p>
</div>'''
        pages[xname(f)] = page(part, body, cls='part-body', epubtype='part')
    else:
        pages[xname(f)] = page(c['title'], body)

# ---------- nav ----------
nav_items = []
cur_part = None
part_blocks = []
for c in chapters:
    f = c['file']
    if f.startswith('0001'): continue
    if re.match(r'^[1-5]000-', f):
        cur_part = {'title': c['title'], 'items': []}
        part_blocks.append(cur_part)
    else:
        item = f'<li><a href="{xname(f)}">{esc(c["title"])}</a></li>'
        if cur_part is not None:
            cur_part['items'].append(item)
        else:
            part_blocks.append({'title': None, 'items': [item]})
nav_lis = []
for b in part_blocks:
    if b['title']:
        nav_lis.append(f'<li><span>{esc(b["title"])}</span><ol>' + ''.join(b['items']) + '</ol></li>')
    else:
        nav_lis.extend(b['items'])
nav = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN" lang="zh-CN">
<head><title>目录</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
<nav epub:type="toc" id="toc"><h1>目录</h1><ol>{''.join(nav_lis)}</ol></nav>
</body>
</html>'''

# ---------- opf ----------
manifest = []
spine = []
for f in order:
    if f.startswith('0001'):
        manifest.append(f'<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>')
        spine.append('<itemref idref="cover"/>')
        continue
    x = xname(f)
    manifest.append(f'<item id="p{stem(f)}" href="{x}" media-type="application/xhtml+xml"/>')
    spine.append(f'<itemref idref="p{stem(f)}"/>')
manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
manifest.append('<item id="css" href="style.css" media-type="text/css"/>')
manifest.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')

modified = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
uid = 'urn:uuid:' + str(uuid.uuid4())
opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid" xml:lang="zh-CN">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="uid">{uid}</dc:identifier>
<dc:title>期权 101</dc:title>
<dc:creator>大马</dc:creator>
<dc:language>zh-CN</dc:language>
<dc:date>2026-11-04</dc:date>
<meta property="dcterms:modified">{modified}</meta>
<meta name="cover" content="cover"/>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine toc="ncx">
{chr(10).join(spine)}
</spine>
</package>'''

# ---------- ncx ----------
navpoints = []
entries = [c for c in chapters if not c['file'].startswith('0001')]
for i, c in enumerate(entries, 1):
    navpoints.append(f'''<navPoint id="np{i}" playOrder="{i}"><navLabel><text>{esc(c['title'])}</text></navLabel><content src="{xname(c['file'])}"/></navPoint>''')
ncx = f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
<head><meta name="dtb:uid" content="{uid}"/><meta name="dtb:depth" content="1"/><meta name="dtb:totalPageCount" content="0"/><meta name="dtb:maxPageNumber" content="0"/></head>
<docTitle><text>期权 101</text></docTitle>
<navMap>{''.join(navpoints)}</navMap>
</ncx>'''

container = '''<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''

# ---------- 写 zip ----------
if os.path.exists(OUT): os.remove(OUT)
with zipfile.ZipFile(OUT, 'w') as z:
    z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
    z.writestr('META-INF/container.xml', container, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr('OEBPS/content.opf', opf, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr('OEBPS/nav.xhtml', nav, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr('OEBPS/toc.ncx', ncx, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr('OEBPS/style.css', css, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr('OEBPS/cover.xhtml', cover, compress_type=zipfile.ZIP_DEFLATED)
    for x, body in pages.items():
        z.writestr('OEBPS/' + x, body, compress_type=zipfile.ZIP_DEFLATED)

# ---------- 校验 ----------
import sys
bad = []
for x, body in pages.items():
    try:
        etree.fromstring(body.encode('utf-8'))
    except Exception as e:
        bad.append((x, str(e)))
for name, data in [('nav', nav), ('opf', opf), ('ncx', ncx), ('container', container)]:
    try:
        etree.fromstring(data.encode('utf-8'))
    except Exception as e:
        bad.append((name, str(e)))
print('章节数:', len(pages), '| 校验失败:', bad if bad else '无')
print('输出:', OUT, os.path.getsize(OUT), 'bytes')
