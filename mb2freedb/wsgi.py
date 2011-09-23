# Copyright (C) 2011 Lukas Lalinsky
# Distributed under the MIT license, see the LICENSE file for details.

# Simple WSGI module intended to be used by uWSGI, e.g.:
# uwsgi -w acoustid.wsgi --pythonpath ~/acoustid/ --env ACOUSTID_CONFIG=~/acoustid/acoustid.conf --http :9090
# uwsgi -w acoustid.wsgi --pythonpath ~/acoustid/ --env ACOUSTID_CONFIG=~/acoustid/acoustid.conf -M -L --socket 127.0.0.1:1717

import os
from mb2freedb.server import make_application

application = make_application(os.environ['MB2FREEDB_CONFIG'])

