"""Websocket/HTTP client to get the status a job."""
from collections import namedtuple
import argparse
from odin.client import ODIN_URL, ODIN_PORT, HttpClient
from odin.utils.formatting import print_table

Row = namedtuple('Row', 'host gpu type free processes pids')


def _gpu2row(gpu, host):
    proc_group = gpu.get('processes', [])
    processes = ' '.join(p['process_name'] for p in proc_group)
    pids = ' '.join(str(p['pid']) for p in proc_group)
    free = 'YES' if len(proc_group) == 0 else 'NO'
    gpu_type = gpu['productName']
    gpu_id = gpu['id'].split(':')[1]
    row = Row(host=host, gpu=gpu_id, type=gpu_type, free=free, processes=processes, pids=pids)
    return row


def request_nodes_http(url: str) -> None:
    """Request the status over HTTP
    :param url: the base URL
    """
    nodes = HttpClient(url).request_cluster_hw_status()
    rows = []

    for node in nodes:
        for gpu in node['gpus']:
            rows.append(_gpu2row(gpu, node['host']))
    print_table(rows)


def main():
    """An HTTP client to request GPU status on a cluster."""
    parser = argparse.ArgumentParser(description="Get GPU status on a cluster over HTTP")
    parser.add_argument('--host', default=ODIN_URL, type=str)
    parser.add_argument('--port', default=ODIN_PORT)
    parser.add_argument(
        '--scheme',
        choices={'http', 'https'},
        default='https',
        help='Connection protocol, supports HTTP and HTTPs',
    )
    args = parser.parse_args()

    url = f'{args.scheme}://{args.host}:{args.port}'
    request_nodes_http(url)


if __name__ == "__main__":
    main()
