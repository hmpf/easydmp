from unittest import TestCase

from easydmp.dmpt.flow import dfs_paths
#from easydmp.dmpt.flow import find_looping_nodes
from easydmp.dmpt.flow import find_start_nodes
from easydmp.dmpt.flow import is_valid_graph_format


class TestIsValidGraph(TestCase):

    def test_empty_graph(self):
        adj_list = {}
        result = is_valid_graph_format(adj_list)
        self.assertTrue(result)

    def test_isolated_nodes(self):
        adj_list = {
            1: set(),
            2: set(),
            3: set(),
        }
        result = is_valid_graph_format(adj_list)
        self.assertTrue(result)

    def test_invalid(self):
        adj_list = {
            1: set((2,3)),
            3: set(),
            4: set((2,3)),
        }
        result = is_valid_graph_format(adj_list)
        self.assertFalse(result)

    def test_valid(self):
        adj_list = {
            1: set((2,3)),
            2: set(),
            3: set(),
            4: set((2,3)),
        }
        result = is_valid_graph_format(adj_list)
        self.assertTrue(result)


class TestFindStarts(TestCase):

    def test_no_starts(self):
        adj_list = {
            1: set((2,3)),
            2: set((1,)),
            3: set(),
        }
        result = find_start_nodes(adj_list)
        self.assertFalse(result)

    def test_starts(self):
        adj_list = {
            1: set((2,3)),
            3: set(),
            4: set((2,3)),
        }
        result = find_start_nodes(adj_list)
        expected = set((1,4))
        self.assertEqual(result, expected)

class TestDFSPaths(TestCase):

    def test_empty(self):
        result = dfs_paths({}, None, None)
        self.assertEqual(list(result), [])

    def test_node_not_in_graph(self):
        adj_list = {
            1: set(),
        }
        result = dfs_paths(adj_list, None, None)
        self.assertEqual(list(result), [])

    def test_single_node(self):
        adj_list = {
            1: set(),
        }
        result = dfs_paths(adj_list, 1, None)
        self.assertEqual(list(result), [(1,)])

    def test_simple(self):
        adj_list = {
            1: set((2,)),
            2: set(),
        }
        result = dfs_paths(adj_list, 1, None)
        expected = [(1, 2)]
        self.assertEqual(list(result), expected)

    def test_explicitness_end_node(self):
        no_explicit_adj_list = {
            1: set((2,3)),
            2: set((3,)),
        }
        result_no_explicit = dfs_paths(no_explicit_adj_list, 1, None)
        explicit_adj_list = {
            1: set((2,3)),
            2: set((3,)),
            3: set(),
        }
        result_explicit = dfs_paths(explicit_adj_list, 1, None)
        self.assertEqual(set(result_no_explicit), set(result_explicit))

    def test_h2020_2_1_1_to_12(self):
        adj_list = {
            1: set([2, 10]),
            2: set([3]),
            3: set([4]),
            4: set([5]),
            5: set([6, 8]),
            6: set([7, 8]),
            7: set([8]),
            8: set([9]),
            9: set([10]),
           10: set([11, 12]),
           11: set([12]),
           12: set([]),
        }
        result = dfs_paths(adj_list, 1, None)
        expected = set([
            (1, 10, 11, 12),
            (1, 10, 12),
            (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
            (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12),
            (1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12),
            (1, 2, 3, 4, 5, 6, 8, 9, 10, 12),
            (1, 2, 3, 4, 5, 8, 9, 10, 11, 12),
            (1, 2, 3, 4, 5, 8, 9, 10, 12),
        ])
        self.assertEqual(set(result), expected)

    def test_h2020_2_1_1_to_10_of_12(self):
        adj_list = {
            1: set([2, 10]),
            2: set([3]),
            3: set([4]),
            4: set([5]),
            5: set([6, 8]),
            6: set([7, 8]),
            7: set([8]),
            8: set([9]),
            9: set([10]),
           10: set([11, 12]),
           11: set([12]),
           12: set([]),
        }
        result = dfs_paths(adj_list, 1, 10)
        expected = set([
            (1, 10),
            (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
            (1, 2, 3, 4, 5, 6, 8, 9, 10),
            (1, 2, 3, 4, 5, 8, 9, 10),
        ])
        self.assertEqual(set(result), expected)

    def test_h2020_2_1_12_to_end(self):
        adj_list = {
           12: set([13]),
           13: set([14]),
           14: set([15, 16]),
           15: set([16]),
           16: set([17, 18]),
           17: set([20]),
           18: set([19]),
           19: set([20]),
           20: set([21, 22]),
           21: set([22]),
           22: set([23, 24]),
           23: set([24]),
           24: set([]),
        }
        result = dfs_paths(adj_list, 12, None)
        expected = set([
            (12, 13, 14, 15, 16, 17, 20, 21, 22, 23, 24),
            (12, 13, 14, 15, 16, 17, 20, 21, 22, 24),
            (12, 13, 14, 15, 16, 17, 20, 22, 23, 24),
            (12, 13, 14, 15, 16, 17, 20, 22, 24),
            (12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23, 24),
            (12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 24),
            (12, 13, 14, 15, 16, 18, 19, 20, 22, 23, 24),
            (12, 13, 14, 15, 16, 18, 19, 20, 22, 24),
            (12, 13, 14, 16, 17, 20, 21, 22, 23, 24),
            (12, 13, 14, 16, 17, 20, 21, 22, 24),
            (12, 13, 14, 16, 17, 20, 22, 23, 24),
            (12, 13, 14, 16, 17, 20, 22, 24),
            (12, 13, 14, 16, 18, 19, 20, 21, 22, 23, 24),
            (12, 13, 14, 16, 18, 19, 20, 21, 22, 24),
            (12, 13, 14, 16, 18, 19, 20, 22, 23, 24),
            (12, 13, 14, 16, 18, 19, 20, 22, 24),
        ])
        self.assertEqual(set(result), expected)
