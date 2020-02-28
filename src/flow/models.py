# encoding: utf-8

from functools import lru_cache
from uuid import uuid4

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db import transaction
from django.db.models import Q

import graphviz as gv

from easydmp.lib.graphviz import _prep_dotsource, view_dotsource, render_dotsource_to_file
from easydmp.lib.models import ClonableModel

from .errors import FSANoStartnodeError
from .errors import FSANoDataError


SLUG_LENGTH = 40


class Node(ClonableModel):
    """
    Defaults, fallbacks; interface for all nodes

    fsa:     which fsa this node belongs to
    slug:    string node name for introspection, must be set
    start:   whether this is the topmost node or not
    end:     whether this is an endnode or not
    depends: node to look up to decide next node. If unset, lookup self

    Reverse relations
    -----------------

    next_nodes, prev_nodes: where to next
    """

    fsa = models.ForeignKey(
        'FSA',
        on_delete=models.CASCADE,
        related_name='nodes'
    )
    slug = models.SlugField(max_length=SLUG_LENGTH)
    start = models.BooleanField(default=False)
    end = models.BooleanField(default=False)
    depends = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ('fsa',)
        unique_together = ('fsa', 'slug')

    @lru_cache(None)
    def __str__(self):  # pragma: no cover
        try:
            return self.payload.legend()
        except (ObjectDoesNotExist, AttributeError):
            pass
        return self.slug

    def clone(self, fsa):
        new = self.__class__(slug=self.slug, fsa=fsa, start=self.start,
                             end=self.end)
        new.set_cloned_from(self)
        new.save()
        return new

    def get_next_node_many(self, next_nodes, data):
        if not data:
            raise FSANoDataError
        depends = self.depends if self.depends else self
        condition = data[str(depends.slug)]
        for edge in next_nodes:
            if depends.slug in data:
                if edge.condition == condition:
                    return edge.next_node
        return None

    def get_next_node(self, nodes):
        if not nodes:
            raise FSANoDataError
        edges = self.next_nodes.all()
        next_nodes = set([edge.next_node for edge in edges])
        if len(next_nodes) == 1:  # simple node
            return next_nodes.pop()
        if len(next_nodes) > 1:  # complex node
            next_node = self.get_next_node_many(edges, nodes)
            return next_node
        # end node or overridden
        return None

    def get_prev_node_many(self, prev_nodes, data):
        if not data:
            raise FSANoDataError
        for edge in prev_nodes:
            prev_node = edge.prev_node
            if prev_node is None:
                return None
            prev_node_slug = prev_node.slug
            if prev_node_slug in data:
                if edge.condition == data[prev_node_slug]:
                    return prev_node
        return None

    def get_prev_node(self, nodes):
        if not nodes:
            raise FSANoDataError
        edges = self.prev_nodes.all()
        prev_nodes = set([edge.prev_node for edge in edges if edge.prev_node])
        if len(prev_nodes) == 1:  # simple node
            return prev_nodes.pop()
        if len(prev_nodes) > 1:  # complex node
            prev_node = self.get_prev_node_many(edges, nodes)
            return prev_node
        # start node or overridden
        return None


class Edge(ClonableModel):
    condition = models.CharField(max_length=64, blank=True)
    prev_node = models.ForeignKey(
        Node,
        on_delete=models.SET_NULL,
        related_name='next_nodes',
        blank=True,
        null=True,
    )
    next_node = models.ForeignKey(
        Node,
        on_delete=models.SET_NULL,
        related_name='prev_nodes',
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ('condition', 'prev_node', 'next_node')

    @lru_cache(None)
    def __str__(self):
        try:
            return self.payload.legend()
        except (ObjectDoesNotExist, AttributeError):
            pass
        me = self.prev_node
        return '{} ({} is "{}") -> {}'.format(
            me, me, self.condition, self.next_node
        )

    def save(self, **kwargs):
        super().save(**kwargs)
        # remove edges without nodes
        if self.prev_node is self.next_node is None:
            self.delete()

    def clone(self, prev, next):
        new = self.__class__(prev_node=prev, next_node=next, condition=self.condition)
        new.set_cloned_from(self)
        new.save()
        return new


class FSA(ClonableModel):
    GRAPHVIZ_TMPDIR = '/tmp/flow_graphviz'

    slug = models.SlugField(max_length=SLUG_LENGTH, unique=True)

    class Meta:
        verbose_name = 'FSA'
        verbose_name_plural = 'FSAs'

    def __str__(self):  # pragma: no cover
        return self.slug

    @transaction.atomic
    def clone(self, slug=None):
        slug = slug if slug else str(uuid4())
        new, created = self.__class__.objects.get_or_create(slug=slug)
        if not created:
            return new
        new.set_cloned_from(self)
        new.save()
        # clone nodes
        mapping = {}
        for node in self.nodes.all():
            mapping[node] = node.clone(new)
        # set depends on nodes
        for node in new.nodes.all():
            node.depends = mapping.get(node.depends, None)
            node.save()
        # clone edges
        for edge in Edge.objects.filter(
            Q(prev_node__in=mapping) | Q(next_node__in=mapping)).distinct():
            edge.clone(
                mapping.get(edge.prev_node, None),
                mapping.get(edge.next_node, None)
            )
        return new

    @property
    def nodemap(self):
        return {s.slug: s for s in self.nodes.all()}

    def get_startnode(self):
        try:
            return Node.objects.get(start=True, fsa=self)
        except Node.DoesNotExist:
            raise FSANoStartnodeError()

    @property
    def start(self):
        "Access the startnode of the FSA"
        return self.get_startnode()

    @start.setter
    def start(self, new_startnode):
        old_startnode = self.get_startnode()
        old_startnode.start = False
        old_startnode.save()
        new_startnode.start = True
        new_startnode.save()

    @start.deleter
    def start(self):
        node = self.get_startnode()
        node.start = False
        node.save()

    def generate_graph(self):
        graph = {}
        for node in self.nodes.all():
            goes_to = set()
            for s in node.next_nodes.all():
                goes_to.add(s.next_node.slug if s.next_node else None)
            graph[node.slug] = list(goes_to)
        return graph

    def _find_all_paths(self, graph, start, path=[]):
        path = path + [start]
        if start is None or self.nodes.get(slug=start).end:
            return [path]
        if start not in graph:
            return []
        paths = []
        for node in graph[start]:
            if node not in path:
                newpaths = self._find_all_paths(graph, node, path)
                for newpath in newpaths:
                    paths.append(newpath)
        return paths

    def find_all_paths(self):
        graph = self.generate_graph()
        paths = self._find_all_paths(graph, self.start.slug)
        return [tuple(path) for path in paths]

    def find_paths_to(self, nodeslug):
        paths = self.find_all_paths()
        paths_to = []
        for path in paths:
            if nodeslug in path:
                pos = path.index(nodeslug)
                paths_to.append(path[:pos])
        paths_to.append(nodeslug)
        return paths

    def find_paths_from(self, nodeslug):
        paths = self.find_all_paths()
        paths_from = []
        for path in paths:
            if nodeslug in path:
                pos = path.index(nodeslug)
                paths_from.append(path[pos:])
        return paths_from

    def nextnode(self, curnode, data):
        "Get next node"
        return self.nodemap[curnode].get_next_node(data)

    def prevnode(self, curnode, data):
        "Get prev node"
        return self.nodemap[curnode].get_prev_node(data)

    def find_possible_paths_for_data(self, data):
        paths = self.find_all_paths()
        candidate_paths = set()
        keys = set(data.keys())
        for path in paths:
            path = tuple(node for node in path if node)
            if keys.issubset(path):
                candidate_paths.add(path)
        return candidate_paths

    def get_maximal_previous_nodes(self, nodeslug, visited=None):
        if not visited:
            visited = set()
        node = Node.objects.get(slug=nodeslug, fsa=self)
        visited.add(node)
        edges = Edge.objects.filter(next_node=node)
        nodes = set(edge.prev_node for edge in edges.all())
        nodes.discard(None)
        for node in nodes.copy():
            if node.start:
                nodes.add(node)
                visited.add(node)
                continue
            if node in visited:
                continue
            recnodes = self.get_maximal_previous_nodes(node.slug, visited)
            nodes = nodes.union(recnodes)
        return list(nodes)

    def order_data(self, data):
        """Sort data according to possible graphs

        Incidentally, removes unknown nodes"""
        paths = self.find_possible_paths_for_data(data)
        # All graphs start the same so just pick one
        keys = paths.pop()
        ordered_data = [(s, data.get(s)) for s in keys if s in data]
        return ordered_data

    def generate_dotsource(self):
        global gv
        dot = gv.Digraph()

        for node in self.nodes.all():
            node_args = {}
            payload = getattr(node, 'payload', None)
            if payload:
                node_args['label'] = payload.label
            if node.start:
                node_args['shape'] = 'doublecircle'
            for edge in Edge.objects.filter(prev_node=node):
                edge_args = {}
                if edge.next_node is None:
                    node_args['shape'] = 'doublecircle'
                    continue
                if edge.condition not in ('', None):
                    edge_args['label'] = edge.condition
                dot.edge(node.slug, edge.next_node.slug, **edge_args)
            dot.node(node.slug, **node_args)
        return dot.source

    def view_dotsource(self, format, dotsource=None):  # pragma: no cover
        if not dotsource:
            dotsource = self.generate_dotsource()
        view_dotsource(format, dotsource, self.GRAPHVIZ_TMPDIR)

    def render_dotsource_to_file(self, format, filename, directory='', dotsource=None):
        _prep_dotsource(self.GRAPHVIZ_TMPDIR)
        if not dotsource:
            dotsource = self.generate_dotsource()
        return render_dotsource_to_file(format, filename, dotsource, self.GRAPHVIZ_TMPDIR, directory)
