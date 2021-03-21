#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

depend_packages=[
       'PySide6',
       'matplotlib',
]

setup(
    name='matplotlibqml',
    version='0.92.001',
    description='Matplotlib Mini QML Backend',
    long_description=open('readme.md').read(),
    long_description_content_type='text/markdown',
    install_requires=depend_packages,
    author='Cong Zhang',
    author_email='congzhangzh@gmail.com',
    maintainer='Cong Zhang',
    maintainer_email='congzhangzh@gmail.com',
    url='https://github.com/medlab/matplotlibqml',
    packages=['matplotlibqml'],
    package_dir={'':'src'},
    package_data={'':['*.qml']},
    #data_files=['gadm/test_datas/testdata.h5'],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)