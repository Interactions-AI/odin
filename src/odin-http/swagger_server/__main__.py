#!/usr/bin/env python3

import logging
import connexion
from typing import Optional, Dict
from swagger_server import encoder
import argparse
from eight_mile.utils import read_config_stream
from mead.utils import convert_path
import asyncio
from swagger_server.models.orm import Dao
import os

ODIN_DB = os.getenv('ODIN_DB', 'odin_db')


def get_db_config(cred: Optional[str]) -> Dict:
    """

    :param cred:
    :return:
    """
    if cred:
        cred_params = read_config_stream(cred)['jobs_db']

    else:
        cred_params = {}
        cred_params['backend'] = os.environ.get("ODIN_JOBS_BACKEND", "postgres")
        cred_params['host'] = os.environ.get("SQL_HOST", "127.0.0.1")
        cred_params['port'] = os.environ.get("DB_PORT", 5432)
        cred_params['user'] = os.environ.get("DB_USER")
        cred_params['passwd'] = os.environ.get("DB_PASS")
    cred_params['db'] = os.environ.get("DB_NAME", "jobs_db")
    return cred_params


class FilterPrometheus(logging.Filter):
    """A logging filter to ignore the fact that Prometheus tries to scrape /metrics."""

    def filter(self, record):
        return not 'GET /metrics' in record.getMessage()


flask_logger = logging.getLogger('werkzeug')
flask_logger.addFilter(FilterPrometheus())

parser = argparse.ArgumentParser(description='odin')
parser.add_argument('--host', default='0.0.0.0', type=str)
parser.add_argument('--port', default='30000')
parser.add_argument('--root_path', help='Root directory', type=convert_path, required=True)
parser.add_argument('--cred', help='Database cred file')
parser.add_argument(
    '--scheme',
    choices={'wss', 'ws'},
    default='wss',
    help='Websocket connection protocol, use `wss` for remote connections and `ws` for localhost',
)
args = parser.parse_args()


def set_cors_headers_on_response(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, X-Requested-With, Content-Type, Accept'
    response.headers['Access-Control-Allow-Methods'] = 'OPTIONS'
    return response


def main():
    app = connexion.App(__name__, specification_dir='./specs/')
    app.app.json_encoder = encoder.JSONEncoder
    app.add_api('odin.yaml', arguments={'title': 'odin API'}, pythonic_params=True)
    app.app.after_request(set_cors_headers_on_response)
    app.app.ws_url = f'{args.scheme}://{args.host}:{args.port}'
    app.app.root_path = args.root_path
    app.app.ws_event_loop = asyncio.new_event_loop()
    creds = get_db_config(args.cred)
    app.app.dao = Dao(dbname=ODIN_DB, **creds)
    app.run(port=9003)


if __name__ == '__main__':
    main()
