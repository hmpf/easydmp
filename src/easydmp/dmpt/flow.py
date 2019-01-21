from dataclasses import dataclass, field
from typing import Optional, Hashable


__all__ = [
    'Transition',
    'TransitionMap',
]

HashableOrNone = Optional[Hashable]
StrOrNone = Optional[str]


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
    transitions: list = field(default_factory=list, init=False)

    def __len__(self):
        return len(self.transitions)

    def add(self, transition):
        category, current, choice, next = transition.astuple()
        if transition not in self.transitions:
            self.transitions.append(transition)
        self.transition_map.setdefault(current, {}).setdefault(choice, {})
        self.transition_map[current][choice].update(category=category, next=next)

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
        transitions = []
        for transition_dict in list_:
            transition = Transition.from_dict(transition_dict)
            transitions.append(transition)
        return cls.from_transitions(*transitions)

    def get_transitions(self, start):
        return self.transition_map[start]

    def select_transition(self, start, condition):
        transitions = self.get_transitions(start)
        if len(transitions) == 1:
            return self.transitions[0]
        try:
            body = transitions[condition]
        except KeyError:
            if not condition:
                condition = None
                body = transitions[condition]
            else:
                raise
        category = body['category']
        next = body['next']
        return Transition(self, category, condition, next)
