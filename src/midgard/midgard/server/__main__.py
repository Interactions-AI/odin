#!/usr/bin/env python3

import connexion
import argparse
import pynvml
from pynvml.smi import nvidia_smi
from midgard.server import encoder

parser = argparse.ArgumentParser(description='midgard')
parser.add_argument('--port', default='29999')
args = parser.parse_args()


def main():
    app = connexion.App(__name__, specification_dir='./swagger/')
    app.app.json_encoder = encoder.JSONEncoder
    app.add_api('swagger.yaml', arguments={'title': 'midgard API'}, pythonic_params=True)
    app.app.nvsmi = nvidia_smi.getInstance()
    app.run(port=args.port)


if __name__ == '__main__':
    main()
