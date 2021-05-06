from __future__ import annotations

from enum import Enum
from typing import List


class Move(str, Enum):
    UP = 'up'
    DOWN = 'down'
    TOP = 'top'
    BOTTOM = 'bottom'


def get_new_index(movement: Move, order: List[int], value) -> int:
    if not order:
        raise ValueError('Empty list')
    last_index = len(order) - 1
    lookup = {Move.UP: -1, Move.TOP: 0, Move.DOWN: +1, Move.BOTTOM: last_index}
    if movement not in lookup.keys():
        raise ValueError('Unsupported movement')
    try:
        index = order.index(value)
    except ValueError:
        raise ValueError('Value not in this order')
    if movement in (Move.UP, Move.TOP) and index == 0:
        raise ValueError('Impossible change')
    if movement in (Move.DOWN, Move.BOTTOM) and index == last_index:
        raise ValueError('Impossible change')
    new_index = lookup[movement]
    if movement in (Move.UP, Move.DOWN):
        new_index = index + new_index
    return new_index


def flat_reorder(order: list, value, new_index: int) -> list:
    new_order = order[:]
    try:
        new_order.remove(value)
    except ValueError:
        return new_order
    new_order.insert(new_index, value)
    return new_order
