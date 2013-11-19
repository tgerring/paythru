#!/usr/bin/env python

from setuptools import setup

setup(name='paythru',
      version='0.7',
      description='paythru.to site code',
      author='Taylor Gerring',
      author_email='taylor.gerring@gmail.com',
      url='http://paythru.to',

      install_requires=[
      	'dnspython',
      	'web.py',
      	'mimerender',
      	'MySQL-python',
      	'python-whois',
            'pyyaml',
            'beautifulsoup4',
            'jsonrpc',
            'twitter',
            'twilio'
      ],

      packages=[
            'lib',
            'lib/bitcoinrpc'
      ],

      py_modules = [
            'paythru',
            'api',
            'main',
            'setup'
      ],

      scripts = [
      ],

      package_data = {
            'lib': ['db_mysql.sql']
      }

     )