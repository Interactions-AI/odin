import pytest
import random
from collections import defaultdict, namedtuple
from functools import reduce
from itertools import chain
from typing import List, NewType
from odin.dag import (
    Graph,
    Node,
    rev_graph,
    topo_sort,
    topo_sort_kahn,
    topo_sort_parallel,
    find_children,
    _find_children,
)


V = namedtuple("V", "name id")
E = namedtuple("E", "src dst")


def is_valid(s: List[Node], tos: Graph) -> bool:
    """Check if a topological soft is valid."""
    for i, x in enumerate(s):
        for e in tos[x]:
            if s.index(e) >= i:
                return False
    return True


def generate_graph(n: int, p: float = 0.5) -> Graph:
    """Generate a random graph with density p."""
    g: Graph = defaultdict(set)
    nodes = list(range(n))
    for f in nodes:
        g[f]
        for t in nodes:
            if f == t:
                continue
            if random.random() > p:
                g[f].add(t)
    return g


def generate_dag(n: int, p: float = 0.5) -> Graph:
    """Generate a Random DAG with density p.

    Generates DAG by creating a list of nodes (this will be a valid topo sort
    for the generated DAG) and then adding links that only go backwards. Given
    that the generated graph will have at least a 1 valid topo sort it must
    be a DAG
    """
    g: Graph = defaultdict(set)
    nodes = list(range(n))
    random.shuffle(nodes)
    for i, n in enumerate(nodes):
        g[n]
        for j in range(i):
            if random.random() < p:
                g[nodes[j]].add(n)
    return g


def test_rev_graph():
    for _ in range(100):
        n = random.randint(50, 200)
        p = random.uniform(0.4, 0.7)
        g = generate_graph(n, p)
        r = rev_graph(g)
        for n in g:
            assert n in r
        for n, es in r.items():
            assert n in g
            for e in es:
                assert n in g[e]


def test_rev_graph_with_empty():
    for _ in range(100):
        n = random.randint(50, 200)
        p = random.uniform(0.4, 0.7)
        g = generate_graph(n, p)
        extra = random.randint(1, 6)
        for _ in range(extra):
            g[len(g)]
        r = rev_graph(g)
        for n in g:
            assert n in r
        for n, es in r.items():
            assert n in g
            for e in es:
                assert n in g[e]


def test_topo_sort():
    for _ in range(100):
        n = random.randint(50, 200)
        p = random.uniform(0.4, 0.7)
        f = generate_dag(n, p=p)
        s = list(chain(*topo_sort_parallel(f)))
        assert is_valid(s, rev_graph(f))


def test_topo_sort_with_empty():
    for _ in range(100):
        n = random.randint(50, 200)
        p = random.uniform(0.4, 0.7)
        f = generate_dag(n, p=p)
        extra = random.randint(1, 6)
        for _ in range(extra):
            f[len(f)]
        s = list(chain(*topo_sort_parallel(f)))
        assert is_valid(s, rev_graph(f))


def test_descendents_are_subsets():
    for _ in range(10):
        graph = generate_dag(100)
        descendents = find_children(graph)
        for node, children in graph.items():
            for child in children:
                assert descendents[child].issubset(descendents[node])


def test_find_descendents():
    graph = defaultdict(set, {0: {1, 2}, 1: {4}, 3: {5}})
    gold_zero = {1, 2, 4}
    zero = _find_children(graph, 0)
    assert zero == gold_zero

    gold_three = {5}
    three = _find_children(graph, 3)
    assert three == gold_three


# Test against clean-room implementation
class G:
    def __init__(self, vertex_list, edge_list):
        self.vertices = vertex_list
        self.edges = edge_list

    def no_incoming(self):
        ids = [v.id for v in self.vertices]
        has_src = set([e.dst for e in self.edges])
        no_in = [no for no in ids if no not in has_src]
        return no_in

    def out_degree(self, vid):
        return len([e.dst for e in self.edges if e.src == vid])

    def in_degree(self, vid):
        return len([e.src for e in self.edges if e.dst == vid])

    def rm_vert(self, vid):
        vertex_list = [v for v in self.vertices if v.id != vid]
        edge_list = [e for e in self.edges if e.src != vid]
        return G(vertex_list, edge_list)

    def get_adj(self, vid):
        return [e.dst for e in self.edges if e.src == vid]

    def empty(self):
        return not self.vertices

    def rev_dir(self):
        vertex_list = [v for v in self.vertices]
        edge_list = [E(e.dst, e.src) for e in self.edges]
        return G(vertex_list, edge_list)


def g_to_graph(g: G) -> Graph:
    nodes = [v.id for v in g.vertices]
    graph: Graph = defaultdict(set)
    for node in nodes:
        graph[node] = [e.dst for e in g.edges if e.src == node]
    return graph


def fork_join_g():
    vertices = [V("A", 1), V("B", 2), V("C", 3), V("D", 4), V("D", 5)]
    edges = [E(4, 5), E(1, 3), E(1, 2), E(3, 4), E(2, 4)]
    return G(vertices, edges)


def topo_lin(g):
    # Store each vertex's in-degree as an array
    in_degrees = {v.id: g.in_degree(v.id) for v in g.vertices}
    output_list = []
    q = g.no_incoming()
    while q:
        next_id = q.pop()
        output_list.append(next_id)
        adj = [e.dst for e in g.edges if e.src == next_id]
        for x in adj:
            in_degrees[x] -= 1
            if in_degrees[x] == 0:
                q.append(x)

    return output_list


def topo_slow(g):
    # step one, identify vertices that have no incoming edge
    # the `in-degree` of these vertices is zero
    output_list = []
    while not g.empty():
        no_in = g.no_incoming()
        if not no_in:
            raise Exception("Not a DAG!")

        selected = no_in[0]
        output_list += [selected]
        g = g.rm_vert(selected)

    return output_list


def test_graph_exact():
    g = fork_join_g()
    graph = g_to_graph(g)
    assert topo_slow(g) == topo_sort(graph)
    assert topo_lin(g) == topo_sort(graph)
