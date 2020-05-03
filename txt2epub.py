#!/usr/bin/env python
#-*- coding: UTF-8 -*-

import sys, os, re, time, pkgutil, logging, fileinput, click, subprocess
from jinja2 import Template, Environment, PackageLoader
from datetime import datetime

__version__ = "1.0"

readme="""
说明:
    将带有简单格式的TXT文件转换为带有目录、作者信息的epub文件。
    然后就可以邮寄到free.kindle.com来下载啦

用法：
    %s [--debug] 紫川.txt  罗浮.txt
"""

class App:
    def __init__(self):
        self.debug = False

    def get_tpl(self, filename):
        return Template(pkgutil.get_data('__main__', filename).decode('utf-8'))

    def convert(self, txt_file):
        if self.debug: logging.basicConfig(level=logging.DEBUG)

        logging.info("Dealing: %s" % txt_file)
        epub_file = txt_file.replace('.txt', '') +".epub"

        meta = {
                'title': '', 'author': '',
                'template': 'templates/book.html',
                'template-ncx': 'templates/book.ncx',
                'template-opf': 'templates/content.opf',
                'isbn': int(time.mktime(datetime.now().timetuple())),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'cover': None, 'chapters': [], 'sections': [],
                }
        state = 'paragraph'
        paras = ['']
        section = {'name':'_', 'paras': paras}
        chapter = {'name':'_', 'sections': [], 'default': section}
        line_style = 0

        for raw in fileinput.input(txt_file):
            try:
                raw = raw.decode('utf-8')
            except:
                raw = raw.decode('gb18030')
            line = raw.replace('\r', '\n').replace('\t', ' ').strip()

            if len(line) < 2: continue

            if line.startswith(u'《'):
                line = line.replace(u'》', '').replace(u'《', '#title:')

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
                    paras = ['']
                    section = {'name': u'_', 'paras': paras}
                    chapter = {'name': chapter_name, 'sections': [], 'default': section}
                    meta['chapters'].append(chapter)
                    line_style = 0  #reset line style
            if section_name:
                section_name = section_name.strip().replace("  ", " ").replace("  ", " ")
                if section_name != section['name']:
                    logging.debug( "\t%s %s" % (len(chapter['sections']), section_name))
                    paras = ['']
                    section = {'name': section_name, 'paras': paras}
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
                if has_space or has_special: paras.append(line)
                else: paras[-1] += line

        logging.info("analyse done: %s. %d Chapters, %d sections" % (
            txt_file, len(meta['chapters']), len(chapter['sections']) )
            )

        if chapter['name'] == '_' and chapter['sections']:  #no chapter
            logging.info('using ARTICLE mode')
            for section in chapter['sections']:
                meta['sections'].append( (section['name'], section['paras']) )

        if len(meta['chapters']) == 0 and len(meta['sections']) > 0:
            logging.info('no chapters, using Article mode. (%d sections)' % len(meta['sections']))
            meta['template'] = 'templates/article.html'
            meta['template-ncx'] = 'templates/article.ncx'

        gen_files = {
                'template': 'book.html',
                'template-ncx': 'book.ncx',
                'template-opf': 'content.opf',
                }
        book_dir = "output"
        try: os.mkdir(book_dir)
        except: pass
        for tag,gen_file in gen_files.items():
            logging.info('generating : %s by %s' % (gen_file, meta[tag]))
            t = self.get_tpl(meta[tag])
            open(os.path.join(book_dir, gen_file), 'w').write(t.render(meta = meta).encode('utf-8'))

        if self.debug: return
        logging.info('Running "ebook-convert" to build .epub file:%s' % epub_file)
        cmd = u'ebook-convert %s "%s" ' % ('book.opf', epub_file.decode("UTF-8"))
        if meta['cover']: cmd += u' --cover "%s"' % meta['cover']
        subprocess.call(cmd, shell=True)

        if os.path.isfile(epub_file) is False:
            logging.erro(" !!!!!!!!!!!!!!!   %s failed  !!!!!!!!!!!!!!" % txt_file)
            return None
        else:
            fsize = os.path.getsize(epub_file)
            logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            logging.info(".epub save as: %s(%.2fMB)" %  (epub_file, fsize/1048576))
            logging.info(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
            return epub_file

@click.command()
@click.option("--debug", is_flag=True, default=False, help="parse txt, but do not convert")
@click.argument("TXT_FILE", nargs=1, type=click.Path(exists=True))
def main(debug, txt_file):
    app = App()
    app.debug = debug
    app.convert(txt_file)

if __name__ == '__main__':
    main()

