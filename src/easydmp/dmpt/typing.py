from typing import Text, Any, TypedDict, MutableMapping, Type, Dict, Tuple, Set, List, Union


__all__ = [
    'AnswerNote',
    'AnswerChoice',
    'Data',
    'PathTuple',
    'AnswerStruct',
]


AnswerNote = Text
AnswerChoice = Any
Data = MutableMapping[str, dict]
PathTuple = Tuple[int, ...]


class AnswerStruct(TypedDict):
    choice: Any
    notes: str
