"""Provides DAG functionality used by chores and k8s job sched
"""
from collections import defaultdict
from copy import deepcopy
from itertools import chain
from typing import DefaultDict, Set, List, NewType, Union
from cachetools import cached
from cachetools.keys import hashkey


Node = NewType('Node', Union[str, int])
Graph = NewType('Graph', DefaultDict[Node, Set[Node]])


def topo_sort(froms: Graph) -> List[Node]:
    """Sort a graph where there is an edge from each key to their values.

    :param froms: A Graph where there exists a directed edge from k to each
        v in Graph[k], k -> v

    :returns: A list of nodes
    """
    tos = rev_graph(froms)
    return topo_sort_kahn(deepcopy(froms), tos)


def topo_sort_parallel(froms: Graph) -> List[Set[Node]]:
    """Sort a graph where there is an edge from key to values.

    :param froms: A Graph where there exists a directed edge from k to each
        v in Graph[k], k -> v

    :returns: A list of sets of nodes where each node in a set can be
        executed in parallel.
    """
    tos = rev_graph(froms)
    return _topo_sort_parallel(tos)


def topo_sort_kahn(froms: Graph, tos: Graph) -> List[Node]:
    """Do a topological sort with Kahn's algo.

    :param froms: A Graph where there exists a directed edge from k to each
        v in Graph[k], k -> v
    :param tos: A Graph where there exists a directed edge from each value
        v in Graph[k] to k, v -> k
    :raises ValueError: If the graph has a cycle in it.
    :returns: The list of nodes in topological order.
    """
    sort = []
    no_ins = set(nd for nd in chain(tos, froms) if not tos[nd])
    while no_ins:
        nd = no_ins.pop()
        sort.append(nd)
        for nd2 in froms[nd]:
            tos[nd2].discard(nd)
            if not tos[nd2]:
                no_ins.add(nd2)
        froms[nd] = set()
    for ed in froms.values():
        if ed:
            raise ValueError('Graph has a cycle')
    return sort


class CycleError(ValueError):
    """An error class to use if the DAG has a cycle in it."""


def _topo_sort_parallel(tos: Graph) -> List[Set[Node]]:
    """Do a topological sort that returns sets of parallel possible jobs.

    :param tos: A Graph where there exists a directed edge from each value
        v in Graph[k] to k, v -> k
    :raises CycleError: If the graph has a cycle in it.
    :returns: A list of sets where each set can be run in parallel.
    """
    sort = []
    while True:
        no_ins = set(n for n, pre in tos.items() if not pre)
        if not no_ins:
            break
        sort.append(no_ins)
        tos = {n: pre - no_ins for n, pre in tos.items() if n not in no_ins}
    if tos:
        raise CycleError('Graph has a cycle')
    return sort


def find_children(froms: Graph) -> DefaultDict[Node, Set[Node]]:
    """Find all the children of all nodes.

    :param froms: A graph where there is an edge from each k to each value v
        in graph[k], k -> v

    :returns: A map for nodes to children.
    """
    return defaultdict(set, {n: _find_children(froms, n) for n in froms})


# The graph is unhashable so we need to stringify it so we can cache it.
@cached(cache={}, key=lambda froms, root: (hashkey(str(froms)), hashkey(root)))
def _find_children(froms: Graph, root: Node) -> Set[Node]:
    """Find all the children of some node.

    :param froms: A graph where there is an edge from each k to each value v
        in graph[k], k -> v
    :param root: The node to collect the children from.

    :returns: The children of `root`
    """
    descendents = set(froms[root])
    for child in froms[root]:
        descendents.update(_find_children(froms, child))
    return descendents


def rev_graph(graph: Graph) -> Graph:
    """Convert a graph from incoming to outgoing.
    :param graph: A graph to reverse
    :returns: A reversed graph
    """
    r_graph = defaultdict(set)
    for nd, eds in graph.items():
        for ed in eds:
            r_graph[ed].add(nd)
        # Make sure this node is in the graph even if it has no edges
        r_graph[nd]  # pylint: disable=W0104
    return r_graph


def dot_graph(froms: Graph) -> str:
    """Convert a graph into a dot string.

    :param froms: A Graph where there exists a directed edge from k to each
        v in Graph[k], k -> v
    :returns: A dot string representing the graph
    """
    lines = ['digraph {']
    for nd, eds in froms.items():
        nd = str(nd).replace('-', '_')
        if not eds:
            lines.append(f"  {nd};")
        for ed in eds:
            ed = str(ed)
            lines.append(f"  {nd} -> {ed.replace('-', '_')};")
    lines.append("}")
    return "\n".join(lines)


def write_graph(froms: Graph, file_name: str) -> None:
    """Write a graph to file in dot format.

    :param froms: A Graph where there exists a directed edge from k to each
        v in Graph[k], k -> v
    :param file_name: A file name to write to
    """
    with open(file_name, 'w') as write_file:
        write_file.write(dot_graph(froms))
