# Copyright (C) 2011 Lukas Lalinsky
# Distributed under the MIT license, see the LICENSE file for details.

import logging
import sqlalchemy
from cgi import parse_qs
from contextlib import closing
from mb2freedb.config import Config
from mb2freedb.utils import LocalSysLogHandler
from mb2freedb.request import CDDB

logger = logging.getLogger(__name__)


class Server(object):

    def __init__(self, config_path):
        self.config = Config(config_path)
        self.engine = sqlalchemy.create_engine(self.config.database.create_url())
        self.setup_logging()

    def setup_logging(self):
        for logger_name, level in sorted(self.config.logging.levels.items()):
            logging.getLogger(logger_name).setLevel(level)
        if self.config.logging.syslog:
            handler = LocalSysLogHandler(ident='mb2freedb',
                facility=self.config.logging.syslog_facility, log_pid=True)
            handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
            logging.getLogger().addHandler(handler)

    def __call__(self, environ, start_response):
        args = parse_qs(environ['QUERY_STRING'])
        with closing(self.engine.connect()) as conn:
            conn.execute("SET search_path TO musicbrainz")
            response = CDDB(self.config, conn).handle(args)
        start_response('200 OK', [
            ('Content-Type', 'text/plain; charset=UTF-8'),
            ('Content-Length', str(len(response)))])
        return [response]


def make_application(config_path):
    app = Server(config_path)
    return app

