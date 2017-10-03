# encoding: utf-8

from pathlib import PurePath, Path

from django.db import models

import graphviz as gv


class Node(models.Model):
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

    fsa = models.ForeignKey('FSA', related_name='nodes')
    slug = models.SlugField(max_length=16)
    start = models.BooleanField(default=False)
    end = models.BooleanField(default=False)
    depends = models.ForeignKey(
        'self',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ('fsa',)
        unique_together = ('fsa', 'slug')

    def __str__(self):  # pragma: no cover
        return self.slug

#     def save(self, *args, **kwargs):
#         if not self.slug:


#     def clone(self, *args, **kwargs):
#         kwargs.pop('force_insert', None)
#         kwargs.pop('force_update', None)
#         suffix = '-clone'
#         self.name = self.name[:16-len(suffix)] + suffix
#         self.save(force_insert=True, *args, **kwargs)
#         return self

    def get_next_node_many(self, next_nodes, data):
        depends = self.depends if self.depends else self
        key = data[str(depends.pk)]['choice']
        next_node = next_nodes.get(condition=key)
        return next_node.next_node

    def get_next_node(self, nodes):
        next_nodes = self.next_nodes.all()
        if next_nodes.count() == 1:  # simple node
            return next_nodes.get().next_node
        elif next_nodes.count() > 1:  # complex node
            return self.get_next_node_many(next_nodes, nodes)
        # end node or overridden
        return None

    def get_prev_node_many(self, prev_nodes, nodes):
        nodes = nodes.copy()
        nodes[self.slug] = None
        paths = self.fsa.find_paths_to(self.slug)
        ordered_nodes = tuple([s[0] for s in self.fsa.order_data(nodes)])
        good_path = None
        for path in paths:
            if path[:len(ordered_nodes)] == ordered_nodes:
                good_path = path
                break
        prev_nodeslug = good_path[good_path.index(self.slug)-1]
        prev_node = self.fsa.nodemap[prev_nodeslug]
        return prev_node

    def get_prev_node(self, nodes):
        prev_nodes = self.prev_nodes.all()
        if prev_nodes.count() == 1:  # simple node
            return prev_nodes.get().prev_node
        elif prev_nodes.count() > 1:  # complex node
            return self.get_prev_node_many(prev_nodes, nodes)
        # start node or overridden
        return None


class Edge(models.Model):
    condition = models.CharField(max_length=64, blank=True)
    prev_node = models.ForeignKey(
        Node,
        related_name='next_nodes',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    next_node = models.ForeignKey(
        Node,
        related_name='prev_nodes',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        unique_together = ('prev_node', 'next_node')

    def __str__(self):
        me = self.prev_node
        return '{} ({} is {}) -> {}'.format(
            me, me, self.condition, self.next_node
        )


class FSA(models.Model):
    GRAPHVIZ_TMPDIR = '/tmp/flow_graphviz'

    slug = models.SlugField(max_length=16)

    class Meta:
        verbose_name = 'FSA'
        verbose_name_plural = 'FSAs'

    def __str__(self):  # pragma: no cover
        return self.slug

    @property
    def nodemap(self):
        return {s.slug: s for s in self.nodes.all()}


    def get_startnode(self):
        return Node.objects.get(start=True, fsa=self)

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
            goes_to = list()
            for s in node.next_nodes.all():
                goes_to.append(s.next_node.slug if s.next_node else None)
            graph[node.slug] = goes_to
        return graph

    def _find_all_paths(self, graph, start, path=[]):
        path = path + [start]
        if start is None or start.end:
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
        # All graphs start the same so just pick one
        keys = self.find_possible_paths_for_data(data).pop()
        ordered_data = [(s, data.get(s)) for s in keys if s in data]
        return ordered_data

    def _prep_dotsource(self):
        """Create workdir for graphviz"""
        path = Path(self.GRAPHVIZ_TMPDIR)
        path.mkdir(mode=0o750, parents=True, exist_ok=True)

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

    def view_dotsource(self, format, dotsource=None): # pragma: no cover
        """Generate and show the fsa structure

        This only makes sense to run on a local computer that has a monitor,
        and depends on the OS recognizing the format to find a program to open
        the result with.

        format: a format supported by graphviz
        doutsource: show dotsource, do not generate from this fsa"""
        self._prep_dotsource()
        if not dotsource:
            dotsource = self.generate_dotsource()
        graph = gv.Source(
            directory=str(self.GRAPHVIZ_TMPDIR),
            source=dotsource,
            format=format,
        )
        graph.view(cleanup=True)

    def render_dotsource_to_file(self, format, filename, directory='', dotsource=None):
        """Generate and store a file of the fsa structure

        This will create a file at <filename> on the computer this software
        runs on.

        format: a format supported by graphviz
        filename: store the file locally at this location
        doutsource: show dotsource, do not generate from this fsa"""
        self._prep_dotsource()
        if not dotsource:
            dotsource = self.generate_dotsource()
        path = PurePath(filename)
        # remove directories, for great paranoia
        filename = path.name
        # The gv library saves as <filename> + <format> so remove any suffix
        filename = filename.stem
        # Add subdir to default dir, if any
        try:
            directory = Path(directory).relative_to(self.GRAPHVIZ_TMPDIR)
        except ValueError:
            directory = Path(self.GRAPHVIZ_TMPDIR)
        directory.mkdir(mode=0o750, exist_ok=True, parents=True)
        graph = gv.Source(
            source=dotsource,
            format=format,
            filename=filename,
            directory=str(directory),
        )
        graph.render(cleanup=True)
        full_path = directory / filename.with_suffix(format)
        return full_path
