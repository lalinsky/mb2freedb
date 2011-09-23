#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from distutils.core import setup
from mb2freedb import __version__

setup(name='mb2freedb',
      version=__version__,
      author='Lukáš Lalinský',
      author_email='lalinsky@gmail.com',
      packages=['mb2freedb'],
      scripts=['mb2freedbd'],
      description='A MusicBrainz FreeDB gateway',
    )

