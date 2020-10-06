#!/usr/bin/env python
#-*- coding: UTF-8 -*-

import sys, os, re, time, pkgutil, logging, fileinput, click, subprocess, zipfile
from jinja2 import Template, Environment, PackageLoader
from datetime import datetime

__version__ = "1.1"

RE_CHAPTER_AND_SECTIONS=[
        u'.*(第.*[卷章部分][ 　：].*)[ 　：](第.*[章节][ 　：]*.*)$',
        u'.*(第.*[卷章部分][ 　：].*)[ 　：](序[ 　：]*幕.*)$',
        ]
RE_CHAPTERS=[
        u'.*(第.{1,8}[卷部分][ 　：].*)$',
        ]
RE_SECTIONS=[
        u'^\s*(后记|番外.*)\s*$',
        u'.*(第.*[章节][ 　：].*)$',
        u'.*(第.*[章节])$',
        u'(尾[ 　：]*声.*)$',
        u'(序[ 　：]*[章幕].*)$',
        ]

RE_TITLE_1=u'^《([^》]*)》$'
RE_TITLE_2=u'^<<([^》]*)>>$'

TAG_REPLACE=[
        (u'简介', "##brief:"),
        (u'内容简介', "##brief:"),
        (u'封面', "#cover:"),
        (u'作者：', "#author:"),
        (u'作者:', "#author:"),
        ]

LINE_STYLE_AUTO=0
LINE_STYLE_APPEND=1
LINE_STYLE_MERGE=2

class App:
    def __init__(self):
        self._idx = 0

    def get_tpl(self, filename):
        from pkg_resources import resource_string
        s = resource_string(__name__, filename).decode("UTF-8")
        return Template( s )

    def idx(self):
        self._idx += 1
        return "%05d" % self._idx

    def build_book(self, epub_file, meta):
        def F(name):
            z = zipfile.ZipInfo(name)
            z.external_attr = 0666 << 16L
            z.compress_type = zipfile.ZIP_DEFLATED
            return z

        epub = zipfile.ZipFile(epub_file, "w", compression=zipfile.ZIP_DEFLATED)

        gen_files = ['book.ncx', 'content.opf', 'mimetype', 'META-INF/container.xml']
        for out in gen_files:
            tpl = self.get_tpl( "templates/" + out )
            txt = tpl.render(meta=meta)
            epub.writestr(F(out), txt.encode('utf-8'))

        tpl = self.get_tpl('templates/book.html')
        out = "welcome.html"
        txt = tpl.render(meta=meta, action="welcome")
        epub.writestr(F(out), txt.encode('utf-8'))

        for chapter in meta['chapters']:
            out = "text/book-chapter-%s.html" % chapter['idx']
            txt = tpl.render(meta=meta, action="chapter", chapter=chapter)
            epub.writestr(F(out), txt.encode('utf-8'))
            for section in chapter['sections']:
                out = "text/book-section-%s.html" % section['idx']
                txt = tpl.render(meta=meta, action="section", section=section)
                epub.writestr(F(out), txt.encode('utf-8'))

        for section in meta['sections']:
            out = "text/book-section-%s.html" % section['idx']
            txt = tpl.render(meta=meta, action="section", section=section)
            epub.writestr(F(out), txt.encode('utf-8'))

    def convert(self, txt_file):
        fsize = os.path.getsize(txt_file)
        logging.info("Input  : %s (%.2fMB)" % (txt_file, fsize/1048576))
        epub_file = txt_file.replace('.txt', '') +".epub"

        meta = {
                'title': '', 'author': '',
                'isbn': int(time.mktime(datetime.now().timetuple())),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'cover': None, 'chapters': [], 'sections': [],
                }
        state = 'paragraph'
        paras = []
        section = {'idx': 0, 'name':'_', 'paras': paras}
        chapter = {'idx': 0, 'name':'_', 'sections': [], 'default': section}
        line_style = LINE_STYLE_AUTO

        for raw in fileinput.input(txt_file):
            try:
                raw = raw.decode('utf-8')
            except:
                raw = raw.decode('gb18030')
            line = raw.replace('\r', '\n').replace('\t', ' ').strip()

            if len(line) < 2: continue

            if line.startswith(u'《') and not meta['title']:
                line = line.split(u'》')[0].strip().replace(u'《', '#title:')

            m = re.match(RE_TITLE_1, line)
            if m is not None and not meta['title']:
                line = '#title:' + m.groups()[0]
            m = re.match(RE_TITLE_2, line)
            if m is not None and not meta['title']:
                line = '#title:' + m.groups()[0]

            for tag_from, tag_to in TAG_REPLACE:
                if line.startswith(tag_from):
                    if tag_to.startswith("##"):
                        line = tag_to + line
                    else:
                        line = line.replace(tag_from, tag_to)

            # 参数值
            m = re.match(u'#([a-z]+):(.*)', line)
            if m is not None:
                tag, val = m.groups()
                meta[tag] = val
                continue

            # 段落内容
            m = re.match(u'##([a-z]+):(.*)', line)
            if m is not None:
                line_style = LINE_STYLE_AUTO  #reset line style
                tag, val = m.groups()
                paras = []
                meta[tag] = paras
                continue

            chapter_name=None
            section_name=None
            # 多个段落内容（例如N个章节）
            m = re.match(u'#@([a-z]+)(:：)(.*)', line)
            if m is not None:
                tag, _, val = m.groups()
                if tag == 'chapter': chapter_name = val
                if tag == 'section': section_name = val

            while True:
                # 猜测章节序号
                m = None
                for r in RE_CHAPTER_AND_SECTIONS:
                    m = re.match(r, line)
                    if m: break
                if m is not None:
                    vals = m.groups()
                    chapter_name = vals[0]
                    section_name = vals[1]
                    break;

                # 猜测章节序号
                m = None
                for r in RE_CHAPTERS:
                    m = re.match(r, line)
                    if m: break
                if m is not None:
                    chapter_name = m.groups()[0]
                    break;

                # 等效与 #@section:
                m = None
                for r in RE_SECTIONS:
                    m = re.match(r, line)
                    if m: break

                if m is not None:
                    section_name = m.groups()[0]
                    break;
                break;

            if chapter_name:
                chapter_name = chapter_name.strip().replace("  ", " ").replace("  ", " ")
                if chapter_name != chapter['name']:
                    logging.debug(u'chapter: %s' % chapter_name)
                    tag = None
                    paras = []
                    section = {'idx': self.idx(), 'name': u'_', 'paras': paras}
                    chapter = {'idx': len(meta['chapters']), 'name': chapter_name, 'sections': [], 'default': section}
                    meta['chapters'].append(chapter)
                    line_style = LINE_STYLE_AUTO  #reset line style

            if section_name:
                section_name = section_name.strip().replace("  ", " ").replace("  ", " ")
                if section_name != section['name']:
                    tag = None
                    paras = []
                    section = {'idx': self.idx(), 'name': section_name, 'paras': paras}
                    chapter['sections'].append(section)
                    logging.debug( "\t%s %s" % (len(chapter['sections']), section_name))
            if chapter_name or section_name:
                continue

            # 处理正文（增加换行检测）
            has_space = raw.startswith(u"    ") or raw.startswith(u"　　")
            has_special = line.startswith("--") or line.startswith("==")
            if line_style == LINE_STYLE_AUTO:
                if has_space: line_style = LINE_STYLE_APPEND
                else: line_style = LINE_STYLE_MERGE
            if line_style == LINE_STYLE_APPEND:
                paras.append(line)
            elif line_style == LINE_STYLE_MERGE:
                if has_space or has_special or len(paras) == 0: paras.append(line)
                else: paras[-1] += line

            if tag == 'brief':
                logging.debug(line)
                logging.debug('\n'.join(meta[tag]))

        logging.info("Result : %s. %d Chapters, %d single sections\nTitle: %s\nAuthor: %s\nBrief: \n%s" % (
            txt_file, len(meta['chapters']), len(meta['sections']),
            meta['title'], meta['author'], "\n".join(meta['brief']),
            ))

        if chapter['name'] == '_' and chapter['sections']:  #no chapter
            meta['sections'].extend( chapter['sections'] )

        self.build_book(epub_file, meta)
        fsize = os.path.getsize(epub_file)
        logging.info("Output : %s(%.2fMB)" %  (epub_file, fsize/1048576))
        return epub_file


@click.command()
@click.option("--debug", is_flag=True, default=False, help="parse txt, but do not convert")
@click.argument("TXT_FILES", nargs=-1, required=True, type=click.Path(exists=True))
def main(debug, txt_files):
    '''将带有简单格式的TXT文件转换为带有目录、作者信息的epub文件。'''
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    app = App()
    for f in txt_files:
        app.convert(f)

if __name__ == '__main__':
    main()

