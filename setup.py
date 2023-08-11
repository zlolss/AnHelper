#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages, Command
from sys import platform as _platform
from shutil import rmtree
import sys
import os

here = os.path.abspath(os.path.dirname(__file__))
NAME = 'anhelper'
REQUIRES_PYTHON = '>=3.0.0'
REQUIRED_DEP = ['adbutils', 'opencv-python', 'flask', 'socketman']
readme = ''
about = {}
history = 'None'
with open(os.path.join(here, 'anhelper', 'version.py')) as f:
    exec(f.read(), about)

with open(os.path.join(here, "README.md"), "rb") as readme_file:
    readme = readme_file.read().decode("UTF-8")

#with open("HISTORY.rst", "rb") as history_file:
#    history = history_file.read().decode("UTF-8")

# OS specific settings
SET_REQUIRES = []
if _platform == "linux" or _platform == "linux2":
   # linux
   print('linux')
elif _platform == "darwin":
   # MAC OS X
   SET_REQUIRES.append('py2app')

required_packages = find_packages()
#required_packages.append('')

APP = [NAME + '.py']
OPTIONS = {
    'argv_emulation': True #,
    #'iconfile': 'icons/app.icns'
}

setup(
    app=APP,
    name=NAME,
    version=about['__version__'],
    description="cap、 touch、 remote control for android via adb",
    long_description=readme + '\n\n' + history,
    long_description_content_type='text/markdown',
    author="zlols",
    author_email='zlols@foxmail.com',
    url='https://github.com/zlolss/AnHelper',
    python_requires=REQUIRES_PYTHON,
    #package_dir={'': '.'},
    packages=required_packages,
    entry_points={
        'console_scripts': [
            #'testrun=testrun:__main__'
            'anhelper-demo = anhelper.demo:main'
        ]
    },
    include_package_data=True,
    install_requires=REQUIRED_DEP,
    license="MIT license",
    zip_safe=False,
    keywords='test',
    classifiers=[
        "Programming Language :: Python :: 3 :: Only",
        "License :: OSI Approved :: MIT License",
        #'Natural Language :: English',
        #'Programming Language :: Python :: 3',
        #'Programming Language :: Python :: 3.3',
        #'Programming Language :: Python :: 3.4',
        #'Programming Language :: Python :: 3.5',
        #'Programming Language :: Python :: 3.6',
        #'Programming Language :: Python :: 3.7',
    ],
    #package_data={'data/predefined_classes.txt': ['data/predefined_classes.txt']},
    options={'py2app': OPTIONS},
    setup_requires=SET_REQUIRES#,
    # $ setup.py publish support.
    #
    #cmdclass={
    #    'upload': UploadCommand,
    #}
)
