import unittest

from easydmp.dmpt.positioning import Move, get_new_index, flat_reorder


class TestGetNewIndex(unittest.TestCase):

    def test_raise_exception_on_empty_order(self):
        with self.assertRaises(ValueError) as e:
            get_new_index(Move.UP, [], None)
        self.assertEqual('Empty list', str(e.exception))

    def test_raise_exception_on_invalid_movement_name(self):
        with self.assertRaises(ValueError) as e:
            get_new_index('bull', [1], None)
        self.assertEqual('Unsupported movement', str(e.exception))

    def test_raise_exception_on_missing_value(self):
        with self.assertRaises(ValueError) as e:
            get_new_index(Move.UP, [1], None)
        self.assertEqual('Value not in this order', str(e.exception))

    def test_raise_exception_on_going_up_when_at_top(self):
        for movement in (Move.UP, Move.TOP):
            with self.assertRaises(ValueError) as e:
                get_new_index(movement, [1, 2], 1)
            self.assertEqual('Impossible change', str(e.exception))

    def test_raise_exception_on_going_down_when_at_bottom(self):
        for movement in (Move.DOWN, Move.BOTTOM):
            with self.assertRaises(ValueError) as e:
                get_new_index(movement, [1, 2], 2)
            self.assertEqual('Impossible change', str(e.exception))

    def test_go_up(self):
        new_index = get_new_index(Move.UP, [1,2,3], 2)
        self.assertEqual(new_index, 0)

    def test_go_down(self):
        new_index = get_new_index(Move.DOWN, [1,2,3], 2)
        self.assertEqual(new_index, 2)

    def test_go_top(self):
        order = [1,2,3]
        for value in order[1:]:
            new_index = get_new_index(Move.TOP, order, value)
            self.assertEqual(new_index, 0)

    def test_go_bottom(self):
        order = [1,2,3]
        for value in order[:-1]:
            new_index = get_new_index(Move.BOTTOM, order, value)
            self.assertEqual(new_index, 2)


class TestFlatReorder(unittest.TestCase):

    def test_reorder_empty_list(self):
        old_order = []
        new_order = flat_reorder(old_order, 1, 1)
        self.assertIsNot(old_order, new_order)
        self.assertEqual(old_order, new_order)

    def test_reorder_single_item_list(self):
        old_order = [5]
        new_order = flat_reorder(old_order, 5, 1)
        self.assertEqual(old_order, new_order)

    def test_reorder_unknown_value(self):
        old_order = [5]
        new_order = flat_reorder(old_order, 'foo', 1)
        self.assertIsNot(old_order, new_order)
        self.assertEqual(old_order, new_order)

    def test_reorder_list(self):
        old_order = ['a', 'b', 'c']
        new_order = flat_reorder(old_order, 'c', 0)
        self.assertIsNot(old_order, new_order)
        self.assertEqual(new_order, ['c', 'a', 'b'])

    def test_reorder_with_invalid_index(self):
        # Redundant, consequence of how list().insert() works
        # Here to demonstrate what happens
        old_order = ['a', 'b', 'c']
        new_order = flat_reorder(old_order, 'c', -9)
        self.assertIsNot(old_order, new_order)
        self.assertEqual(new_order, ['c', 'a', 'b'])
        new_order = flat_reorder(old_order, 'c', 9)
        self.assertIsNot(old_order, new_order)
        self.assertEqual(new_order, ['a', 'b', 'c'])
