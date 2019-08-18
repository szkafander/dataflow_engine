# -*- coding: utf-8 -*-
# Main Workspace engine.

import abc
import common

from common import NamedList, IterableProp, PriorityList
from typing import Any, Callable, Iterable, List, Optional, Tuple, Union
from types import ModuleType


class EngineError(Exception): pass
class EngineAttributeError(EngineError): pass

class SkipType: pass
class TouchType: pass


class Function:
    """ Class for functions. A Function object holds references to a Callable 
    function, its inputs (gets), outputs (sets) and callbacks (triggers). When 
    a Function object is called, the stored function is called on the inputs 
    and the outputs are set to the returned value. Optional callbacks can be 
    defined that are automatically called when the function completes. """

    gets = IterableProp("_gets", PriorityList)
    sets = IterableProp("_sets", PriorityList)
    triggers = IterableProp("_triggers", PriorityList)
    
    def __init__(
            self, 
            function: Callable, 
            gets: Optional[Union[
                "Variable", 
                PriorityList["Variable"]
            ]] = None,
            sets: Optional[Union[
                "Variable", 
                PriorityList["Variable"]
            ]] = None,
            triggers: Optional[Union[
                "Function", 
                PriorityList["Variable"]
            ]] = None,
            name: Optional[str] = None,
            description: Optional[str] = None
        ) -> None:
        """ Constructor.

        :param function: A Callable that is run when the Function is called.
        :type function: Callable
        :param gets: A Variable or a tuple of Variables that are the inputs of 
            the function. They are passed as arguments in the order they appear
            in the tuple.
        :type gets: Optional[Union["Variable", Tuple["Variable",...]]]
        :param sets: A Variable or a tuple of Variables that are the outputs of
            the function. They are set in the order they appear in the tuple.
        :type sets: Optional[Union["Variable", Tuple["Variable",...]]]
        :param triggers: A Function or a tuple of Functions that are run when 
            the function completes.
        :type triggers: Optional[Union["Function", Tuple["Function",...]]]
        :param description: An optional string that describes the Function.
        :type description: str
        
        """
        self.function = function
        self.gets = gets
        self.sets = sets
        self.triggers = triggers
        self.description = description
        if name is None:
            self.name = self.function.__name__
        else:
            self.name = name
    
    def __repr__(self):
        return "{} <- {}({})".format(
                self.sets.list_repr() if len(self.sets) != 0 else "()",
                self.name, 
                self.gets.list_repr()
            )
    
    def __str__(self):
        return self.__repr__()

    def __call__(self):
        self.call()
    
    def sort_edges(self) -> None:
        self.sets.sort_by_priority()
        self.gets.sort_by_priority()
        self.triggers.sort_by_priority()

    def call(self):
        """ Runs the functions with the proper inputs. The returned value
        will be set as the value of the outputs.

        Casting the inputs is evident and is done in the order in which 
        they appear in self.sets.

        Casting the outputs happens by running the function and collecting 
        the returned values. Behavior is as follows:

            * If a tuple T is returned and len(T) == len(self.sets), then
                self.sets[i].value = T[i]. 
            * If a tuple T is returned and len(T) > 1 and len(self.sets) == 1,
                then self.sets[0] = T.
            * If a single value A is returned and len(self.sets) == 1, then 
                self.sets[0] = A.
            * All other cases raise EngineAttributeError.
        
            * If any value of T or A is SkipType, for that value, the corresponding output will not be set.
            * If any value of T or A is TouchType, for that value, the 
                corresponding output will be touched (its triggers will fire, 
                but its value will not be set).

        """
        args = [input_.value for input_ in self.gets]
        outputs = self.function(*args)
        outputs = common._make_iterable(outputs, tuple)
        n_outputs = len(outputs)
        n_sets = len(self.sets)
        if n_outputs == n_sets:
            # cast one-by-one
            mode_1by1 = True
        elif n_sets == 1:
            # cast all to one
            mode_1by1 = False
        else:
            raise EngineAttributeError(("No suitable dispatch mode could be ", "inferred. The number of outputs from the function: {}, the ", "number of output Variables: {}.").format(n_outputs, n_sets))
        # dispatch mode check
        if mode_1by1:
            for k, output in enumerate(outputs):
                # if output is SkipType, do not touch Variable
                if output is SkipType:
                    pass
                elif output is TouchType:
                    self.sets[k].touch()
                else:
                    self.sets[k].set_value(output)
        else:
            if output is SkipType:
                pass
            elif output is TouchType:
                self.sets[k].touch()
            else:
                self.sets[k].set_value(outputs)
        # fire callbacks if any
        for function in self.triggers:
            function.call()


class Variable:
    """ Class for variables. A Variable holds its value and a NamedList of
    Functions that are triggered when the value of the Variable is set. """

    triggers = IterableProp("_triggers", PriorityList)
    
    def __init__(
            self, 
            name: str, 
            value: Optional[Any] = None, 
            triggers: Optional[Union[Function, PriorityList[Function]]] = None,
            description: Optional[str] = None
        ) -> None:
        """ Constructor.

        :param name: The name of the Variable.
        :type name: str
        :param value: The value of the Variable.
        :type value: Any
        :param triggers: A Function or a tuple of Functions that are run when the Variable is set or touched.
        :type triggers: Optional[Union["Function", Tuple["Function",...]]]
        :param description: An optional string that describes the Variable.
        :type description: str

        """
        self.name = name
        self._value = value
        self.triggers = triggers
        self.description = description
        
    def __repr__(self) -> str:
        value = str(self.value)
        value = (value[:20] + "...") if len(value) > 20 else value
        return "{}({})".format(self.name, value)
    
    def __str__(self) -> str:
        return self.__repr__()

    @property
    def value(self) -> Any:
        """ self.value = x is an alias for self.set_value(x). """
        return self._value
    
    @value.setter
    def value(self, value) -> None:
        self.set_value(value)
    
    def set_value(self, value: Any) -> None:
        """ Sets the value of the Variable and triggers Functions.

        :param value: The new value of the Variable.
        :type value: Any

        """
        self._value = value
        for function in self.triggers:
            function.call()
    
    def skip(self, *args) -> None:
        """ This is called when e.g., a SkipType value is returned by a 
        Function. The Variable is not updated and triggers are not fired. """
        pass
    
    def touch(self, *args) -> None:
        """ This is called when e.g., a TouchType value is returned by a
        Function. The Variable is not updated but triggers are fired. """
        for function in self.triggers:
            function.call()
    
    def sort_edges(self) -> None:
        self.triggers.sort_by_priority()


class Workspace:
    """ Workspace class that is a container of Functions and Variables.
    Normally produced by parsing.pull_gml. .functions and .variables are
    contained in NamedLists.
    
    To access a specific function or variable, use .functions[<name>] or
    .variables[<name>]. """

    variables = IterableProp("_variables", NamedList)
    functions = IterableProp("_functions", NamedList)

    def __init__(
            self, 
            variables: Optional[NamedList] = None, 
            functions: Optional[NamedList] = None,
            description: Optional[str] = None
        ) -> None:
        self.variables = variables
        self.functions = functions
        self.description = description

    def add_variable(self, variable: Variable) -> None:
        self.variables.append(variable.name, variable)
    
    def add_function(self, function: Function) -> None:
        self.functions.append(function.name, function)
