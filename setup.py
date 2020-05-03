#!/usr/bin/env python
#-*- coding:utf-8 -*-

from setuptools import setup, find_packages
import txt2epub

setup(
    name = "txt2epub",
    version = txt2epub.__version__,
    url = "https://github.com/talebook/txt2epub",
    author = 'Rex Liao',
    author_email = 'talebook@foxmail.com',
    description = 'Auto detect the structure of TXT, and convert to epub',
    long_description = open("README").read(),
    license = 'BSD',
    install_requires = ['jinja2', 'click'],
    py_modules=['txt2epub'],
    entry_points = {
        'console_scripts': [
            'txt2epub = txt2epub:main',
        ]
    }
)
