"""Websocket/HTTP client to get the status a job."""
from collections import namedtuple
import argparse
from eight_mile.utils import is_sequence
from muninn import ODIN_URL, ODIN_PORT, ODIN_SCHEME, HttpClient
from muninn.formatting import print_table

Row = namedtuple('Row', 'host gpu type free power util memuse processes pids ')


def _gpu2row(gpu, host):
    proc_group = gpu.get('processes', [])
    if is_sequence(proc_group):
        processes = ' '.join(p['process_name'] for p in proc_group)
        pids = ' '.join(str(p['pid']) for p in proc_group)
        free = 'YES' if len(proc_group) == 0 else 'NO'
        used_memory = sum([int(p['used_memory']) for p in proc_group])
    else:
        processes = 'NA'
        pids = 'NA'
        free = 'NA'
        used_memory = -1
    power = '{: >4}/{}{}'.format(int(gpu['powerReadings']['powerDraw']), int(gpu['powerReadings']['powerLimit']), gpu['powerReadings']['unit'])
    gpu_type = gpu['productName'].replace('GeForce ', '')
    util = '{}{}'.format(gpu['utilization']['gpuUtil'], gpu['utilization']['unit']) if gpu['utilization']['gpuUtil'] else ''
    gpu_id = gpu['id'].split(':')[1]
    row = Row(host=host, gpu=gpu_id, type=gpu_type, free=free, power=power, util=util, memuse='{}M'.format(used_memory) if used_memory else '', processes=processes, pids=pids)
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
        '--scheme', choices={'http', 'https'}, default=ODIN_SCHEME, help='Connection protocol, supports HTTP and HTTPs',
    )
    args = parser.parse_args()

    url = f'{args.scheme}://{args.host}:{args.port}'
    request_nodes_http(url)


if __name__ == "__main__":
    main()
