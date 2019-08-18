# -*- coding: utf-8 -*-
# Common methods and classes.

import collections

from tabulate import tabulate
from typing import Any, Iterable, Generic, List, Tuple, TypeVar, Union


ReturnType = TypeVar("ReturnType")


def set_dict_value(dic: dict, keys: Tuple[str,...], value: Any) -> None:
    """ Sets a value in a nested dict without having to initialize nested
    sub-dicts. """

    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def get_dict_value(dic: dict, keys: Tuple[str,...]) -> Any:
    """ Gets a value in a nested dict based on a list of keys. """

    value = dic
    for key in keys:
        if key in value:
            value = value[key]
        else:
            return False
    return value


def _is_iterable(value: Any) -> bool:
    try:
        iter(value)
    except TypeError:
        return False
    return True


def _make_iterable(value: Any, iterable_type: type):
    if value is None:
        return iterable_type()
    else:
        return iterable_type((value,)) if not _is_iterable(value) else value


def _sort_indices(array: Iterable) -> List[int]:
    """ Returns sorting indices i of a so that sorted(a) = a[i]. """
    return [i[0] for i in sorted(enumerate(array), key=lambda x: x[1])]


class Prop:

    def __init__(self, property_name: str) -> None:
        self.property_name = property_name

    def __get__(self, instance: Any, owner: type) -> Iterable:
        return getattr(instance, self.property_name)

    def __set__(self, instance: Any, value: Any) -> None:
        setattr(instance, self.property_name, value)


class IterableProp(Prop):
    """ A helper class that defines a descriptor that enforces a property to be 
    an Iterable. If the property is:

        * None: an empty tuple is set.
        * any value x that is not an Iterable: (x,) is set.
        * an Iterable: it is set unchanged.

    The setter invokes the method _make_iterable.

    """
    def __init__(self, property_name: str, iterable_type: type = tuple) -> None:
        super(IterableProp, self).__init__(property_name)
        self.iterable_type = iterable_type

    def __set__(self, instance: Any, value: Any) -> None:
        setattr(
            instance,
            self.property_name,
            _make_iterable(value, self.iterable_type)
        )


class NamedList(Generic[ReturnType]):
    """ This is a container that is:

        * Indexible by numerical index
        * Indexible by a string key
        * Supports append and pop
        * Supports iteration
    
    This is used as a container for Variables and Functions in Workspaces. It
    allows referencing via Variable and Function names.

    """

    def __init__(self, **kwargs: Any) -> None:
        self._values = list(kwargs.values())
        self._keys = list(kwargs.keys())
        self._n = 0

    def _get_ind(self, index: Union[int, str]) -> str:
        if isinstance(index, str):
            return self._keys.index(index)
        return index
    
    def __getitem__(self, index: Union[int, str]) -> ReturnType:
        return self._values[self._get_ind(index)]
    
    def __setitem__(self, index: Union[int, str], value: Any) -> None:
        self._values[self._get_ind(index)] = value
    
    def __len__(self):
        return len(self._values)
    
    def __iter__(self):
        self._n = 0
        return self

    def __next__(self):
        if self._n < len(self):
            val = self[self._n]
            self._n += 1
            return val
        else:
            raise StopIteration
    
    def __contains__(self, other: str) -> bool:
        return other in self._keys
    
    def append(self, keyword: str, value: Any) -> None:
        if keyword not in self._keys:
            self._keys.append(keyword)
            self._values.append(value)
        else:
            raise ValueError(("Keyword {} already in NamedList with "
            "value {}.").format(keyword, self[keyword]))
    
    def pop(self, index: Union[int, str]) -> Any:
        ind = self._get_ind(index)
        self._keys.pop(index)
        return self._values.pop(ind)
    
    def sort_by_value(self) -> None:
        inds = _sort_indices(self._values)
        self._values = [self._values[i] for i in inds]
        self._keys = [self._keys[i] for i in inds]

    def __repr__(self) -> str:
        if len(self) != 0:
            return tabulate(
                [[i, *c] for i, c 
                    in enumerate(zip(self._keys, self._values))],
                headers=["id", "key", "val"],
                numalign="left",
                stralign="left"
            )
        return "empty NamedList"
    
    def list_repr(self) -> str:
        return ", ".join([str(val) for val in self._values])
    

class PositiveInfinity(int):

    def __lt__(self, other: int) -> bool:
        return False
    
    def __repr__(self) -> str:
        return "+inf"


class NegativeInfinity(int):

    def __lt__(self, other: int) -> bool:
        return True
    
    def __repr__(self) -> str:
        return "-inf"


pos_inf = PositiveInfinity()
neg_inf = NegativeInfinity()


class PriorityList(Generic[ReturnType]):
    """ This is a container that is:

        * Indexible by a numerical index
        * Supports sorting by an independent integer priority
        * Supports append and pop
        * Supports iteration

    This is used as a container for .sets, .gets and .triggers. This allows
    sorting these callbacks based on edge order.

    .sets, .gets and .triggers do not have priority attributes because instances
    cannot be copied because then copies are not references of each other.

    """

    def __init__(self, *args: Any) -> None:
        self._priorities = [i for i in range(len(args))]
        self._values = list(args)
        self._n = 0
    
    def __getitem__(self, index: int) -> ReturnType:
        return self._values[index]
    
    def __setitem__(self, index: int, value: Any) -> None:
        self._values[index] = value
    
    def __len__(self):
        return len(self._values)
    
    def __iter__(self):
        self._n = 0
        return self

    def __next__(self):
        if self._n < len(self):
            val = self[self._n]
            self._n += 1
            return val
        else:
            raise StopIteration
    
    def __contains__(self, other: Any) -> bool:
        return other in self._values
    
    def append(self, priority: int, value: Any) -> None:
        # TODO - insorting?
        self._priorities.append(priority)
        self._values.append(value)
    
    def pop(self, index: int) -> Any:
        self._priorities.pop(index)
        return self._values.pop(index)

    def sort_by_priority(self) -> None:
        inds = _sort_indices(self._priorities)
        self._priorities = [self._priorities[i] for i in inds]
        self._values = [self._values[i] for i in inds]

    def __repr__(self) -> str:
        if len(self) != 0:
            return tabulate(
                [[i, *c] for i, c 
                    in enumerate(zip(self._priorities, self._values))],
                headers=["id", "priority", "val"],
                numalign="left",
                stralign="left"
            )
        return "empty PriorityList"
    
    def list_repr(self) -> str:
        return ", ".join([str(val) for val in self._values])
