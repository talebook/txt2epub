#!/usr/bin/env python
#-*- coding: UTF-8 -*-

import sys, os, re, time, pkgutil, logging, fileinput, click, subprocess, zipfile
from jinja2 import Template, Environment, PackageLoader
from datetime import datetime

__version__ = "1.0"

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
        line_style = 0

        for raw in fileinput.input(txt_file):
            try:
                raw = raw.decode('utf-8')
            except:
                raw = raw.decode('gb18030')
            line = raw.replace('\r', '\n').replace('\t', ' ').strip()

            if len(line) < 2: continue

            if line.startswith(u'《') and not meta['title']:
                line = line.split(u'》')[0].strip().replace(u'《', '#title:')

            m = re.match(u'^《([^》]*)》$', line)
            if m is not None and not meta['title']:
                line = '#title:' + m.groups()[0]
            m = re.match(u'^<<([^》]*)>>$', line)
            if m is not None and not meta['title']:
                line = '#title:' + m.groups()[0]
            if line.startswith(u'简介') or line.startswith(u'内容简介'):
                line = '##brief:' + line
            if line.startswith(u'封面：'):
                line = line.replace(u'封面：', '#cover:')
            if line.startswith(u'作者：'):
                line = line.replace(u'作者：', '#author:')

            # 参数值
            m = re.match(u'#([a-z]+):(.*)', line)
            if m is not None:
                tag, val = m.groups()
                meta[tag] = val
                continue

            # 段落内容
            m = re.match(u'##([a-z]+):(.*)', line)
            if m is not None:
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
                m = re.match(u'.*(第.*[卷章部分][ 　：].*)[ 　：](第.*[章节][ 　：]*.*)$', line)
                if m is None:
                    m = re.match(u'.*(第.*[卷章部分][ 　：].*)[ 　：](序[ 　：]*幕.*)$', line)
                if m is not None:
                    vals = m.groups()
                    chapter_name = vals[0]
                    section_name = vals[1]
                    break;

                # 猜测章节序号
                m = re.match(u'.*(第.{1,8}[卷部分][ 　：].*)$', line)
                if m is not None:
                    vals = m.groups()
                    chapter_name = vals[0]
                    break;

                m = re.match(u'^\s*(后记|番外.*)\s*$', line)
                if m is not None:
                    section_name = m.groups()[0]

                # 等效与 #@section:
                m = re.match(u'.*(第.*[章节][ 　：].*)$', line)
                if m is None:
                    m = re.match(u'.*(第.*[章节])$', line)
                if m is None:
                    m = re.match(u'(尾[ 　：]*声.*)$', line)
                if m is None:
                    m = re.match(u'(序[ 　：]*[章幕].*)$', line)
                if m is not None:
                    section_name = m.groups()[0]
                    break;
                break;
            if chapter_name:
                chapter_name = chapter_name.strip().replace("  ", " ").replace("  ", " ")
                if chapter_name != chapter['name']:
                    logging.debug(u'chapter: %s' % chapter_name)
                    paras = []
                    section = {'idx': self.idx(), 'name': u'_', 'paras': paras}
                    chapter = {'idx': len(meta['chapters']), 'name': chapter_name, 'sections': [], 'default': section}
                    meta['chapters'].append(chapter)
                    line_style = 0  #reset line style

            if section_name:
                section_name = section_name.strip().replace("  ", " ").replace("  ", " ")
                if section_name != section['name']:
                    logging.debug( "\t%s %s" % (len(chapter['sections']), section_name))
                    paras = []
                    section = {'idx': self.idx(), 'name': section_name, 'paras': paras}
                    chapter['sections'].append(section)
            if chapter_name or section_name:
                continue

            # 处理正文（增加换行检测）
            has_space = raw.startswith(u"    ") or raw.startswith(u"　　")
            has_special = line.startswith("--") or line.startswith("==")
            if line_style == 0:
                if has_space: line_style = 2
                else: line_style = 1
            elif line_style == 1:
                paras.append(line)
            elif line_style == 2:
                if has_space or has_special or len(paras) == 0: paras.append(line)
                else: paras[-1] += line

        logging.info("Result : %s. %d Chapters, %d sections" % (
            txt_file, len(meta['chapters']), len(chapter['sections']) )
            )

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

