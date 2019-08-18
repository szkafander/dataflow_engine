# -*- coding: utf-8 -*-
# Methods that parse .gml files into Workspaces.

import abc

from common import IterableProp
from common import pos_inf, neg_inf, get_dict_value, set_dict_value
from engine import EngineError
from engine import Function, Variable, Workspace
from typing import Any, Callable, List, Optional, Tuple, Union
from types import ModuleType


class Relation(abc.ABC):

    @abc.abstractstaticmethod
    def match(a: Any, b: Any) -> bool:
        pass
    
    @abc.abstractmethod
    def __repr__(self) -> str:
        pass
    
    @abc.abstractmethod
    def __str__(self) -> str:
        pass


class Contains(Relation):
    
    @staticmethod
    def match(a: Any, b: Any) -> bool:
        return b in a
    
    def __repr__(self) -> str:
        return "contains"
    
    def __str__(self) -> str:
        return self.__repr__()


class Equals(Relation):
    
    @staticmethod
    def match(a: Any, b: Any) -> bool:
        return a == b
    
    def __repr__(self) -> str:
        return "equals"
    
    def __str__(self) -> str:
        return self.__repr__()


class DoesNotEqual(Relation):
    
    @staticmethod
    def match(a: Any, b: Any) -> bool:
        return a != b
    
    def __repr__(self) -> str:
        return "equals"
    
    def __str__(self) -> str:
        return self.__repr__()


class NestedField:

    fields = IterableProp("_fields", tuple)

    def __init__(self, *args: str) -> None:
        self.fields = args
    
    def __repr__(self) -> str:
        return "/" + "/".join(self.fields)


equals = Equals()
does_not_equal = DoesNotEqual()
contains = Contains()


class Word:

    def __init__(self, string: str) -> None:
        self.string = string
    
    def __eq__(self, other: Any) -> bool:
        return self.string == other
    
    def __ne__(self, other: Any) -> bool:
        return self.string != other
    
    def __contains__(self, other: Any) -> bool:
        return other in self.string


class PREDEFS:
    """ Pre-defined fields and values common in gml files. """

    class FIELDS:

        NODE_TYPE = NestedField("graphics", "type")
        COLOR = NestedField("graphics", "fill")
        EDGE_TYPE = NestedField("graphics", "type")
        EDGE_STYLE = NestedField("graphics", "style")
        EDGE_WIDTH = NestedField("graphics", "width")
        EDGE_COLOR = NestedField("graphics", "fill")
    
    class VALUES:

        RED = Word("#FF0000")
        BLUE = Word("#0000FF")
        GREEN = Word("#00FF00")
        DASHED = Word("dashed")
        DASHDOT = Word("dashed-dotted")
        RECTANGLE = Word("rectangle")
        ROUNDRECTANGLE = Word("roundrectangle")
        ELLIPSE = Word("ellipse")
        TRIANGLEUP = Word("triangle")
        TRIANGLEDOWN = Word("triangle2")


class Pattern:
    """ Class that defines a matching pattern for graph parsing. A pattern is a 
    key-value pair. The key can be nested and is always a Iterable of strings.
    A value can be anything, but most often an int, float or string. """

    fields = IterableProp("_fields", tuple)
    relations = IterableProp("_relations", tuple)
    values = IterableProp("_values", tuple)

    def __init__(
            self, 
            fields: Union[NestedField, Tuple[NestedField,...]],
            relations: Union[Relation, Tuple[Relation,...]],
            values: Union[Any, Tuple]
        ) -> None:
        """ Constructor.

        :param field: The name of the field or nested fields to look for.
        :type field: Union[str, Tuple[str], Tuple[Tuple[str]]]
        :param relation: Abstract relation that matches fields with values.
        :type value: Relation
        
        """
        self.fields = fields
        self.relations = relations
        self.values = values
        self._check_dimensions()
    
    def _check_dimensions(self) -> None:
        if not (
            len(self.fields) == len(self.relations) and
            len(self.relations) == len(self.values)
        ):
            raise ValueError(("The same number of fields, relations and "
                "values must be passed."))

    def __str__(self) -> str:
        repr = ["{} {} {}".format(
            self.fields[i], 
            str(self.relations[i]), 
            self.values[i]
        ) for i in range(len(self.fields))]
        return "pattern:\n" + " & \n".join(repr)
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __add__(self, other: "Pattern") -> "Pattern":
        return Pattern(
            (*self.fields, *other.fields),
            (*self.relations, *other.relations),
            (*self.values, *other.values)
        )
    
    def match(self, other: dict) -> bool:
        is_match = True
        for i, relation in enumerate(self.relations):
            is_match = is_match and relation.match(
                get_dict_value(other, self.fields[i].fields),
                self.values[i]
            )
        return is_match


config = {
    # this field contains field names that specify the top-level
    # graph. no multigraphs are allowed, thus the .gml should only
    # contain one graph entry. this graph entry is identified by
    # matching graph_spec.graph.
    "graph_spec": {
        "graph": "graph",
        "node": "node",
        "edge": "edge",
        "node_id": "id",
        "edge_id": "source",
        "stepped_fields": ("node", "edge")
    },
    "node_spec": {
        "ind": "id",
        "name": "label",
        "name_token": "@",
        "name_separator": " "
    },
    "edge_spec": {
        "order": "label",
        "default_order": pos_inf,
        "source": "source",
        "target": "target"
    },
    "parsing": {
        "apostrophe": '"',
        "separator": "\t",
        "bracket_open": "[",
        "bracket_close": "]",
        "default_variable_value": 0
    },
    "patterns": {
        "variable": Pattern(
            PREDEFS.FIELDS.NODE_TYPE, 
            equals,
            PREDEFS.VALUES.ELLIPSE
        ),
        "function": Pattern(
            PREDEFS.FIELDS.NODE_TYPE,
            equals,
            PREDEFS.VALUES.ROUNDRECTANGLE
        ),
        "gets": Pattern(
            PREDEFS.FIELDS.COLOR,
            equals,
            PREDEFS.VALUES.BLUE
        ) + Pattern(
            PREDEFS.FIELDS.EDGE_STYLE,
            equals,
            False
        ),
        "sets": Pattern(
            PREDEFS.FIELDS.COLOR,
            equals,
            PREDEFS.VALUES.GREEN
        ) + Pattern(
            PREDEFS.FIELDS.EDGE_STYLE,
            equals,
            False
        ),
        "triggers": Pattern(
            PREDEFS.FIELDS.COLOR,
            equals,
            PREDEFS.VALUES.RED
        ) + Pattern(
            PREDEFS.FIELDS.EDGE_STYLE,
            equals,
            False
        )
    }
}


def interpret_value(value: str) -> Union[int, float, str]:
    """ Attempts to interpret a string as an integer or float. 
    If not possible, returns the string. """

    if value[0] == config["parsing"]["apostrophe"]:
        value = value[1:]
    if value[-1] == config["parsing"]["apostrophe"]:
        value = value[:-1]
    try:
        return int(value)
    except:
        try:
            return float(value)
        except:
            return value


def preprocess_line(line: str) -> str:
    """ Removes trailing whitespace and end-line. """

    return line.strip().replace("\n", "")


# These are classes for identifying line patterns in .gml-like text files
class ParseOutput: pass


class _SingleString(ParseOutput):

    def __init__(self, string: str) -> None:
        self.string = string


class _SingleWord(_SingleString): pass
class _BracketOpen(_SingleString): pass
class _BracketClose(_SingleString): pass
class _Continuation(_SingleString): pass
class _ContinuationEnds(_SingleString): pass


class _ContinuationStarts(ParseOutput):

    def __init__(self, field: str, string: str) -> None:
        self.field = field
        self.string = string


class _ValidKeyVal(ParseOutput):

    def __init__(self, field: str, string: str) -> None:
        self.field = field
        self.string = string


class _InvalidKeyVal(ParseOutput): pass


def parse_line(line: str, continued: bool = False) -> ParseOutput:
    """ Parses text line into a key and value. If not possible, raises an EngineIoError.

    :param line: The line to separate.
    :type line: str
    :param continued: True if line is a continuation of a previous line.
    :type continued: bool
    :returns: The parsed line.
    :rtype: ParseOutput

    """

    separator = config["parsing"]["separator"]
    bracket_open = config["parsing"]["bracket_open"]
    bracket_close = config["parsing"]["bracket_close"]

    separated = line.split(separator)
    no_items = len(separated)
    if not continued:
        if no_items == 2:
            if separated[1].find('"') == 0 and separated[1].rfind('"') == 0:
                return _ContinuationStarts(separated[0], separated[1])
            elif separated[1] == '""' or separated[1] == "''":
                return _InvalidKeyVal()
            else:
                return _ValidKeyVal(separated[0], separated[1])
        elif no_items == 1:
            if separated[0] == bracket_open:
                return _BracketOpen(bracket_open)
            elif separated[0] == bracket_close:
                return _BracketClose(bracket_close)
            else:
                return _SingleWord(line)
        else:
            raise ValueError("Invalid line: {}".format(line))
    else:
        line_length = len(line) - 1
        if line.find('"') == line_length and line.rfind('"') == line_length:
            return _ContinuationEnds(line)
        else:
            return _Continuation(line)


def read_gml(path: str) -> dict:
    """ Reads a .gml file into a nested dict. Fields that are in STEPPED_FIELDS will be renamed by adding a running index.

    :param path: The path to the .gml file.
    :type path: str
    :returns: A nested dict representation of the .gml.
    :rtype: dict

    """

    result = {}
    fields = []
    continued = False
    n_fields = {field: 0 for field in config["graph_spec"]["stepped_fields"]}

    def format_field(field):
        nonlocal n_fields
        if field in n_fields:
            n_fields[field] += 1
            # this assumes no whitespaces at linebreaks and adds one
            return field + "_{}".format(n_fields[field])
        else:
            return field

    with open(path) as f:
        for line in f:
            parsed = parse_line(preprocess_line(line), continued)
            if isinstance(parsed, _SingleWord):
                field = format_field(parsed.string)
                fields.append(field)
            elif isinstance(parsed, _BracketClose):
                fields.pop()
            elif isinstance(parsed, _ContinuationStarts):
                continued = True
                field = parsed.field
                val = parsed.string
            elif isinstance(parsed, _Continuation):
                val += " " + parsed.string
            elif isinstance(parsed, _ContinuationEnds):
                continued = False
                val += " " + parsed.string
                set_dict_value(result, fields + [field], interpret_value(val))
            elif isinstance(parsed, _ValidKeyVal):
                field = parsed.field
                val = parsed.string
                set_dict_value(result, fields + [field], interpret_value(val))
            elif isinstance(parsed, _BracketOpen):
                continue
            elif isinstance(parsed, _InvalidKeyVal):
                continue
            else:
                raise ValueError("Invalid parse output encountered. Parse output: {}.".format(parsed))
    
    return result


def get_nodes_and_edges(graph_dict: dict) -> Tuple[List, List]:
    """ Gets lists of nodes and edges from a graph dictionary. The lists are
    sorted based on node_id_expr and edge_id_expr, by node ID's and edge 
    sources by default. """

    graph_dict = graph_dict[config["graph_spec"]["graph"]]
    nodes = [val for key, val in graph_dict.items() 
        if config["graph_spec"]["node"] in key]
    edges = [val for key, val in graph_dict.items() 
        if config["graph_spec"]["edge"] in key]
    nodes.sort(key=lambda x: x[config["graph_spec"]["node_id"]])
    edges.sort(key=lambda x: x[config["graph_spec"]["edge_id"]])
    return nodes, edges


def parse_label(label: str) -> Tuple[str, str]:

    token = config["node_spec"]["name_token"]
    separator = config["node_spec"]["name_separator"]

    if label.count(token) != 1:
        raise ValueError(("Label is improperly formatted: it contains more ","than one name token ({}).").format(token))
    ind_separator = label.find(separator)
    if ind_separator == -1:
        name = label[label.find(token)+1:]
        description = ""
    else:
        name = label[label.find(token)+1:ind_separator+1]
        description = label[label.find(separator)+1:]
    return name, description


def variable_from_definitions(
        definitions: ModuleType, 
        params: dict
    ) -> Variable:
    label = params[config["node_spec"]["name"]]
    name, description = parse_label(label)
    value = getattr(definitions, name)
    return Variable(name, value, description=description)


def function_from_definitions(
        definitions: ModuleType,
        params: dict
    ) -> Function:
    label = params[config["node_spec"]["name"]]
    name, description = parse_label(label)
    function = getattr(definitions, name)
    return Function(function, name=name, description=description)


def get_edge_order(edge: dict) -> int:
    try:
        return edge[config["edge_spec"]["order"]]
    except:
        return config["edge_spec"]["default_order"]


def get_entity(params: dict) -> str:

    entities = list(config["patterns"].keys())
    patterns = list(config["patterns"].values())

    matches = [pattern.match(params) for pattern in patterns]
    if matches.count(True) == 1:
        return entities[matches.index(True)]
    else:
        return None


def setup_workspace(
        nodes: List[dict], 
        edges: List[dict],
        definitions: Union[ModuleType, str]
    ) -> Workspace:
    """ Reads a .gml and returns a Workspace object.

    Parsing rules:

        * Two node types are recognized: Variables and Functions
        * Edges set up .gets, .sets and .triggers of Variables and Functions
        * Edges can have integer labels, these specify the priority or order of
            Functions and Variables
        * The .gml is interpreted based on the passed Parser, NodeSpec and 
            EdgeSpec
    
    """

    if isinstance(definitions, str):
        definitions = __import__(definitions)
    
    # init workspace
    workspace = Workspace()

    # scan nodes
    _id_dict = {}
    ind = config["node_spec"]["ind"]
    for node in nodes:
        matched = get_entity(node)
        if matched == "variable":
            variable = variable_from_definitions(definitions, node)
            workspace.add_variable(variable)
            _id_dict.update({node[ind]: variable})
        elif matched == "function":
            function = function_from_definitions(definitions, node)
            workspace.add_function(function)
            _id_dict.update({node[ind]: function})

    # scan edges
    for edge in edges:
        matched = get_entity(edge)
        target_id = edge[config["edge_spec"]["target"]]
        source_id = edge[config["edge_spec"]["source"]]
        priority = get_edge_order(edge)
        if matched == "gets":
            _id_dict[target_id].gets.append(priority, _id_dict[source_id])
        if matched == "sets":
            _id_dict[source_id].sets.append(priority, _id_dict[target_id])
        if matched == "triggers":
            _id_dict[source_id].triggers.append(priority, _id_dict[target_id])
    
    # order edges
    for variable in workspace.variables:
        variable.sort_edges()
    
    for function in workspace.functions:
        function.sort_edges()
    
    return workspace


def pull_gml(
        gml_name: str,
        definitions: Union[ModuleType, str]
    ) -> Workspace:
    """ The main method that parses a .gml into a Workspace object. 
    
    :param gml_name: The path to the .gml file.
    :type gml_name: str
    :param definitions: A module or path to a module that contains definitions
        for all Functions and Variables.
    :type definitions: Union[ModuleType, str]
    :param parser: The Parser object that recognizes the node/edge type.
    :type parser: Optional[Parser]
    :param node_spec: A NodeSpec object that holds relevant fieldnames for 
        nodes.
    :type node_spec: Optional[NodeSpec]
    :param edge_spec: An EdgeSpec object that holds relevant fieldnames for
        edges.
    :type edge_spec: Optional[EdgeSpec]
    :returns: A parsed Workspace object.
    :rtype: Workspace
    
    """

    gml = read_gml(gml_name)
    nodes, edges = get_nodes_and_edges(gml)
    return setup_workspace(nodes, edges, definitions)
