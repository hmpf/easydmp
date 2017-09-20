# encoding: utf-8

from __future__ import unicode_literals

from django import test
from datetime import date

from flow.models import Node
from flow.models import Edge
from flow.models import FSA


def generate_nodes(start, **canned_data):
    s1 = Node.objects.create(slug='s1', **canned_data)
    s2 = Node.objects.create(slug='s2', **canned_data)
    s3 = Node.objects.create(slug='s3', **canned_data)
    s4 = Node.objects.create(slug='s4', **canned_data)
    s5 = Node.objects.create(slug='s5', **canned_data)
    nodes = {
        'start': start,
        's1': s1,
        's2': s2,
        's3': s3,
        's4': s4,
        's5': s5,
    }
    srstart1 = Edge.objects.create(prev_node=start, next_node=s1)
    sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
    sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
    sr24 = Edge.objects.create(prev_node=s2, next_node=s4)
    sr34 = Edge.objects.create(prev_node=s3, next_node=s4)
    sr45 = Edge.objects.create(prev_node=s4, next_node=s5)
    sr5end = Edge.objects.create(prev_node=s5)
    return nodes


class CannedData(object):

    def setUp(self):
        self.fsa = FSA.objects.create(slug='FSA')
        self.start = Node.objects.create(slug='start', fsa=self.fsa, start=True)
        self.canned_data = {
            'fsa': self.fsa,
        }


class TestNodeNextnodeMethods(CannedData, test.TestCase):

    def test_no_nextstate(self):
        s = Node.objects.create(slug='s', **self.canned_data)
        result = s.get_next_node(None)
        self.assertEqual(result, None)

    def test_branching_nextnode(self):
        s1 = Node.objects.create(slug='s1', **self.canned_data)
        s2 = Node.objects.create(slug='s2', **self.canned_data)
        s3 = Node.objects.create(slug='s3', **self.canned_data)
        sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
        sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
        s1_pk = str(s1.pk)
        with self.assertRaises(Edge.DoesNotExist):
            result_None = s1.get_next_node({s1_pk: {'choice': None}})
        result_True = s1.get_next_node({s1_pk: {'choice': True}})
        self.assertEqual(result_True, s2)
        result_False = s1.get_next_node({s1_pk: {'choice': False}})
        self.assertEqual(result_False, s3)

    def test_branching_depends_nextnode(self):
        s0 = Node.objects.create(slug='s0', **self.canned_data)
        s1 = Node.objects.create(slug='s1', depends=s0, **self.canned_data)
        s2 = Node.objects.create(slug='s2', **self.canned_data)
        s3 = Node.objects.create(slug='s3', **self.canned_data)
        sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
        sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
        s0_pk = str(s0.pk)
        with self.assertRaises(Edge.DoesNotExist):
            result_None = s1.get_next_node({s0_pk: {'choice': None}})
        result_True = s1.get_next_node({s0_pk: {'choice': True}})
        self.assertEqual(result_True, s2)
        result_False = s1.get_next_node({s0_pk: {'choice': False}})
        self.assertEqual(result_False, s3)


class TestNodePrevNodeTestCase(CannedData, test.TestCase):

    def test_xor_multiple_prevnode(self):
        """
        s1 -> s2
        s1 -> s3
        s2 -> s4
        s3 -> s4
        """
        s1 = Node.objects.create(slug='s1', **self.canned_data)
        s2 = Node.objects.create(slug='s2', **self.canned_data)
        s3 = Node.objects.create(slug='s3', **self.canned_data)
        s4 = Node.objects.create(slug='s4', **self.canned_data)
        sr1 = Edge.objects.create(next_node=s1)
        sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
        sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
        sr24 = Edge.objects.create(condition=False, prev_node=s2, next_node=s4)
        sr34 = Edge.objects.create(condition=False, prev_node=s3, next_node=s4)
        sr4end = Edge.objects.create(condition=False, prev_node=s4)
        self.fsa.start = s1
        self.fsa.save()
        result_True = s4.get_prev_node({'s1': {'choice': True}, 's2': {'choice': None}})
        self.assertEqual(result_True, s2)
        result_True = s4.get_prev_node({'s1': {'choice': False}, 's3': {'choice': None}})
        self.assertEqual(result_True, s3)

    def test_shortcut_multiple_prevnode(self):
        """
        s1 -> s2
        s1 -> s3
        s2 -> s3
        """
        s1 = Node.objects.create(slug='s1', **self.canned_data)
        s2 = Node.objects.create(slug='s2', **self.canned_data)
        s3 = Node.objects.create(slug='s3', **self.canned_data)
        sr1 = Edge.objects.create(next_node=s1)
        sr12 = Edge.objects.create(condition=True, prev_node=s1, next_node=s2)
        sr13 = Edge.objects.create(condition=False, prev_node=s1, next_node=s3)
        sr23 = Edge.objects.create(prev_node=s2, next_node=s3)
        sr3end = Edge.objects.create(condition=False, prev_node=s3)
        self.fsa.start = s1
        self.fsa.save()
        result_True = s3.get_prev_node({'s1': {'choice': True}, 's2': {'choice': None}})
        self.assertEqual(result_True, s2)
        result_False = s3.get_prev_node({'s1': {'choice': False}})
        self.assertEqual(result_False, s1)


class TestFSA(CannedData, test.TestCase):

    def setUp(self):
        super(TestFSA, self).setUp()
        self.fsa.save()

    def generate_nodes(self):
        self.nodes = generate_nodes(self.start, **self.canned_data)

    def test_find_all_paths_one_node(self):
        srstart = Edge.objects.create(prev_node=self.start, next_node=None)
        self.assertEqual(self.fsa.find_all_paths(), [(self.start.slug, None)])

    def test_find_all_paths(self):
        self.generate_nodes()
        paths = self.fsa.find_all_paths()
        route1 = (self.start.slug, 's1', 's2', 's4', 's5', None)
        route2 = (self.start.slug, 's1', 's3', 's4', 's5', None)
        self.assertEqual(set(paths), set((route1, route2)))
        self.assertNotEqual(route1, route2)

    def test_get_maximal_previous_nodes(self):
        self.generate_nodes()
        result = self.fsa.get_maximal_previous_nodes('s4')
        self.assertEqual(len(result), 4)

    def test_find_possible_paths_for_data(self):
        self.generate_nodes()
        expected_path = ('start', 's1', 's2', 's4', 's5')
        data = {k: None for k in expected_path[:3]}
        result = self.fsa.find_possible_paths_for_data(data)
        self.assertEqual(result, set((expected_path,)))
        bad_path = ('start', 's1', 's4', 's5')
        data = {k: None for k in bad_path}
        result = self.fsa.find_possible_paths_for_data(data)
        self.assertEqual(len(result), 2)

    def test_order_data(self):
        self.generate_nodes()
        expected = [('start', None), ('s1', None), ('s2', None)]
        data = dict(expected)
        result = self.fsa.order_data(data)
        self.assertEqual(result, expected)

    def test_generate_dotsource(self):
        self.generate_nodes()
        source = self.fsa.generate_dotsource()
        self.assertIn('start [shape=doublecircle]', source)
        self.assertIn('s5 [shape=doublecircle]', source)
