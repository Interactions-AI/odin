#!/usr/bin/env python3

import connexion
import argparse
import logging

from midgard.server import encoder
flask_logger = logging.getLogger('werkzeug')
parser = argparse.ArgumentParser(description='midgard')
parser.add_argument('--port', default='29999')
args = parser.parse_args()


def main():
    app = connexion.App(__name__, specification_dir='./swagger/')
    app.app.json_encoder = encoder.JSONEncoder
    app.add_api('swagger.yaml', arguments={'title': 'midgard API'}, pythonic_params=True)

    try:
        import pynvml
        from pynvml.smi import nvidia_smi
        app.app.nvsmi = nvidia_smi.getInstance()
    except Exception as e:
        flask_logger.error("Failed to load NVML.  This node cannot produce GPU information", exc_info=True)
        app.app.nvsmi = None
    app.run(port=args.port)


if __name__ == '__main__':
    main()
