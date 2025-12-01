#!/usr/bin/env python3
#-*- coding:utf-8 -*-

from setuptools import setup, find_packages

setup(
    name             = "txt2epub",
    version          = "1.0.3",
    url              = "https://github.com/talebook/txt2epub",
    author           = 'Rex Liao',
    author_email     = 'talebook@foxmail.com',
    description      = 'Auto detect the structure of TXT, and convert to epub',
    long_description = open("README.md").read(),
    license          = 'BSD',
    packages         = ['txt2epub'],
    package_dir      = {'txt2epub': 'src'},
    package_data     = {'txt2epub': ['templates/*', 'templates/*/*']},
    install_requires = ['jinja2',   'click'],
    #py_modules=['txt2epub'],
    entry_points = {
        'console_scripts': [
            'txt2epub = txt2epub.txt2epub:main',
        ]
    }
)
