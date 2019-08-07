#!/usr/bin/env python

import os
import sys

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()


from setuptools import setup, Extension


with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='noonlight',
    version='0.1.1',
    packages=['noonlight'],
    url='https://github.com/konnected-io/noonlight-py',
    license="MIT License",
    description='A Python library for interacting with the Noonlight API',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Nate Clark, Nick Gordon, Konnected Inc',
    author_email='help@konnected.io',
    install_requires=['aiohttp'],
    project_urls={
      'Homepage': 'https://github.com/konnected-io/noonlight-py',
      'API Documentation': 'https://docs.noonlight.com'
    }
)