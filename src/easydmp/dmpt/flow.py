from dataclasses import dataclass, field
from itertools import chain
import logging
from typing import Optional, Hashable


__all__ = [
    'Transition',
    'TransitionMap',
]
LOG_TRACE = 5

LOG = logging.getLogger(__name__)
LOG.trace = lambda *args, **kwargs: LOG.log(LOG_TRACE, *args, **kwargs)  # type: ignore


HashableOrNone = Optional[Hashable]
StrOrNone = Optional[str]


def flatten(list_of_lists):
    return chain.from_iterable(list_of_lists)


def is_valid_branching_graph(graph):
    """Checks if a graph is correct for branching

    * No isolated nodes
    * Exactly one start node
    * All nodes visited also have a key in the adjacency list
    * TBD: No cycles
    """
    valid_format = is_valid_graph_format(graph)
    start_nodes = find_start_nodes(graph)
    any_isolated = bool(find_isolated_nodes(graph))
    return valid_format and len(start_nodes) == 1 and not any_isolated


def is_valid_graph_format(graph):
    """Checks for graph format validity

    The graph is valid iff all next nodes are represented as keys in the
    adjacency list.
    """
    starts = set(graph.keys())
    nexts = set(flatten(graph.values()))
    return starts.issuperset(nexts)


def find_start_nodes(graph):
    nodes = set(graph.keys())
    adjacent = flatten(graph.values())
    starts = nodes.difference(adjacent)
    return starts


def find_end_nodes(graph):
    return set(k for k, v in graph.items() if not v)


def find_isolated_nodes(graph):
    isolated = set()
    for node in graph:
        if not graph[node]:
            isolated.add(node)
    return isolated


def dfs_paths(graph, start, end=None):
    """Find all paths in digraph, return a generator of tuples

    Input: adjacency list in a dict:

    {
        node1: set([node1, node2, node3]),
        node2: set([node2, node3]),
        node3: set(),
    }
    """
    if not graph or start not in graph:
        return
        yield  # Empty generator
    stack = [(start, [start])]
    while stack:
        node, path = stack.pop()
        if not graph.get(node, None):
            yield tuple(path)
            continue
        if end and node == end:
            yield tuple(path)
            continue
        for next in graph[node] - set(path):
            if not next:
                yield tuple(path) + (next,)
            else:
                stack.append((next, path + [next]))


def dfs_paths_from_to(graph, start, end=None):
    all_paths = dfs_paths(graph, start, end)
    if end is None:
        return all_paths
    paths = []
    for path in all_paths:
        if end in path:
            paths.append(path)
    return paths


@dataclass(frozen=True)
class Transition:
    category: str = field()
    current: Hashable = field()
    choice: StrOrNone = field()
    next: HashableOrNone = field()

    def to_dict(self):
        "Convert to a dict of primitive objects suitable for serialization"
        return self.__dict__

    @classmethod
    def from_dict(cls, transition_dict):
        "Convert the result of to_dict back to a Transition"
        return cls(
            transition_dict['category'],
            transition_dict['current'],
            transition_dict['choice'],
            transition_dict['next'],
        )

    def astuple(self):
        "Convert to a primitive tuple, for quick unpacking"
        return (self.category, self.current, self.choice, self.next)


@dataclass
class TransitionMap:
    transition_map: dict = field(default_factory=dict, repr=False, init=False)
    transitions: set = field(default_factory=set, init=False)

    def __len__(self) -> int:
        return len(self.transitions)

    def __contains__(self, transition: Transition) -> bool:
        if self.select_transition(transition.current, transition.choice):
            return True
        return False

    def as_bare_adjacency_list(self):
        """Adjacency list made up of only the nodes

        Mostly for debugging.
        """
        adj_list = {}
        for transition in self.transitions:
            adj_list.setdefault(transition.current, set())
            adj_list[transition.current].add(transition.next)
        return adj_list

    def add(self, transition):
        LOG.trace('TransitionMap before adding %s: %s', transition, self)
        category, current, choice, next = transition.astuple()
        self.transition_map.setdefault(current, {}).setdefault(choice, {})
        existing = self.select_transition(current, choice)
        if existing is not None:
            try:
                self.transitions.remove(existing)
            except KeyError:
                pass
        self.transition_map[current][choice].update(
            category=category,
            next=next,
            transition=transition
        )
        self.transitions.add(transition)
        LOG.trace('TransitionMap after adding %s: %s', transition, self)

    @classmethod
    def from_transitions(cls, *transitions):
        map = cls()
        map.transition_map = {}
        for transition in transitions:
            map.add(transition)
        return map

    def to_list(self):
        "Convert to a list of primitive objects suitable for serialization"
        serializable_transition_list = []
        for transition in self.transitions:
            serializable_transition_list.append(transition.__dict__)
        return tuple(serializable_transition_list)

    @classmethod
    def from_list(cls, list_):
        "Convert the result of to_list back to a TransitionMap"
        transitions = set()
        for transition_dict in list_:
            transition = Transition.from_dict(transition_dict)
            transitions.add(transition)
        return cls.from_transitions(*transitions)

    def get_transitions(self, start):
        return self.transition_map.get(start, None)

    def select_transition(self, start, condition):
        if not self.transitions:
            return None
        transitions = self.get_transitions(start)
        if not transitions:
            return None
        if not condition in transitions:
            condition = None
        body = transitions.get(condition, None)
        if body is None:
            return None
        return body.get('transition', None)

    def find_paths(self, start, end=None):
        assert start in self.transition_map
        adjacencies = {}
        for transition in self.transitions:
            adjacencies.setdefault(transition.current, set()).add(transition.next)
        paths = tuple(dfs_paths_from_to(adjacencies, start, end))
        if not paths:
            raise ValueError('There are no paths between {} and {}'.format(
                             start, end))
        return paths
