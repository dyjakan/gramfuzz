#!/usr/bin/env python
# encoding: utf-8


"""
This module defines all of the core gramfuzz fields:

* Float
* UFloat
* Int
* UInt
* Join
* Opt
* Or
* Q
* Ref
* String

Each field has a ``build()`` method, which accepts one argument
(pre) that can be used to assign prerequisites of the build result.
"""


from collections import deque
import json
import inspect
import os


from gramfuzz import GramFuzzer
import gramfuzz.errors as errors
import gramfuzz.rand as rand
import gramfuzz.utils as utils


class MetaField(type):
    """Used as the metaclass of the core ``Field`` class. MetaField
    defines ``__and__`` and ``__or__`` and ``__repr__`` methods.
    The overridden and and or operatories allow classes themselves
    to be wrapped in an `And` or `Or` without having to instantiate
    them first.

    E.g. the two lines below are equivalent: ::python
        
        And(Int(), Float())
        (Int & Float)

        Or(Int(), Float())
        (Int | Float)

    Do note however that this can only be done if the first (farthest
    to the left) operand is a Field class or instance.

    E.g. the first line below will work, but the second line will not will not: ::python

        Or(5, Int)
        5 | Int

    It is also recommended that using the overloaded ``&`` and ``|`` operators should
    only be done in very simple cases, since it is impossible for the code
        to know the difference between the two statements below: ::python

            (Int | Float) | Uint
            Int | Float | UInt
    """

    def __and__(self, other):
        """Wraps this field and the other field in an ``And``
        """
        if isinstance(other, And) and other.rolling:
            other.values.append(self)
            return other
        else:
            return And(self, other, rolling=True)

    def __or__(self, other):
        """Wraps this field and the other field in an ``Or``
        """
        if isinstance(other, Or) and other.rolling:
            other.values.append(self)
            return other
        else:
            return Or(self, other, rolling=True)
    
    def __repr__(self):
        return "<{}>".format(self.__name__)

class Field(object):
    """The core class that all field classes are based one. Contains
    utility methods to determine probabilities/choices/min-max/etc.
    """

    __metaclass__ = MetaField

    min = 0
    max = 0x100

    odds = []
    """``odds`` is a list of tuples that define probability values.
    
    Each item in the list must be a tuple of the form: ::python

        (X, Y)

    Where ``X`` is the probability percent, and where ``Y`` is one of
    the following:

    * A single value
    * A list/tuple containing two values, the min and max of a range of numbers.

    Note that the sum of each probability percent in the list must equal 1.0.
    """

    def __and__(self, other):
        """Wrap this field and the other field in an ``And``

        :param  other: Another ``Field`` class, instance, or python object to ``Or`` with
        """
        if isinstance(self, And) and self.rolling:
            self.values.append(other)
            return self
        elif isinstance(other, And) and other.rolling:
            other.values.append(self)
            return other
        else:
            return And(self, other, rolling=True)

    def __or__(self, other):
        """Wrap this field and the other field in an ``Or``

        :param  other: Another ``Field`` class, instance, or python object to ``Or`` with
        """
        if isinstance(self, Or) and self.rolling:
            self.values.append(other)
            return self
        elif isinstance(other, Or) and other.rolling:
            other.values.append(self)
            return other
        else:
            return Or(self, other, rolling=True)
    
    def _odds_val(self):
        """Determine a new random value derived from the
        defined ``self.odds`` value.

        :returns: The derived value
        """
        if len(self.odds) == 0:
            self.odds = [(1.00, [self.min, self.max])]

        rand_val = rand.random()
        total = 0
        for percent,v in self.odds:
            if total <= rand_val < total+percent:
                found_v = v
                break
            total += percent

        res = None
        if isinstance(v, (tuple,list)):
            rand_func = rand.randfloat if type(v[0]) is float else rand.randint

            if len(v) == 2:
                res = rand_func(v[0], v[1])
            elif len(v) == 1:
                res = v[0]
        else:
            res = v

        return res
    
    def __repr__(self):
        res = "<{}".format(self.__class__.__name__)
        if hasattr(self, "values"):
            res += "[" + ",".join(repr(v) for v in self.values)
            res += "]"
        res += ">"
        return res


class Int(Field):
    """Represents all Integers, with predefined odds that target
    boundary conditions.
    """

    min = 0
    max = 0x10000003
    neg = True

    odds = [
        (0.75,    [0,100]),
        (0.05,    0),
        (0.05,    [0x80-2,0x80+2]),
        (0.05,    [0x100-2,0x100+2]),
        (0.05,    [0x10000-2, 0x10000+2]),
        (0.03,    0x80000000),
        (0.02,    [0x100000000-2, 0x100000000+2])
    ]

    def __init__(self, value=None, **kwargs):
        """Create a new Int object, optionally specifying a hard-coded value

        :param int value: The value of the new int object
        :param int min: The minimum value (if value is not specified)
        :param int max: The maximum value (if value is not specified)
        :param list odds: The probability list. See ``Field.odds`` for more information.
        """
        self.value = value

        if "min" in kwargs or "max" in kwargs:
            self.odds = []

        self.min = kwargs.setdefault("min", self.min)
        self.max = kwargs.setdefault("max", self.max)
        self.odds = kwargs.setdefault("odds", self.odds)
    
    def build(self, pre=None):
        """Build the integer, optionally providing a ``pre`` list
        that *may* be used to define prerequisites for a Field being built.

        :param list pre: A list of prerequisites to be collected during the building of a Field.
        """
        if pre is None:
            pre = []

        if self.value is not None and rand.maybe():
            return utils.val(self.value, pre)

        if self.min == self.max:
            return self.min

        res = self._odds_val()
        if self.neg and rand.maybe():
            res = -res
        return res


class UInt(Int):
    """Defines an unsigned integer ``Field``.
    """
    neg = False

class Float(Int):
    """Defines a float ``Field`` with odds that define float
    values
    """
    odds = [
        (0.75,    [0.0,100.0]),
        (0.05,    0),
        (0.10,    [100.0, 1000.0]),
        (0.10,    [1000.0, 100000.0]),
    ]
    neg = True

class UFloat(Float):
    """Defines an unsigned float field.
    """
    neg = False

class String(UInt):
    """Defines a string field
    """
    min = 0
    max = 0x100

    odds = [
        (0.85,    [0,20]),
        (0.10,    1),
        (0.025,    0),
        (0.025,    [20,100]),
    ]
    """Unlike numeric ``Field`` types, the odds value for the ``String`` field
    defines the *length* of the field, not characters used in the string.

    See the ``Field.odds`` for details on the format of the ``odds`` probability
    list.
    """

    charset_alpha_lower = "abcdefghijklmnopqrstuvwxyz"
    """A lower-case alphabet character set
    """

    charset_alpha_upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    """An upper-case alphabet character set
    """

    charset_alpha = charset_alpha_lower + charset_alpha_upper
    """Upper- and lower-case alphabet
    """

    charset_spaces = "\n\r\t "
    """Whitespace character set
    """

    charset_num = "1234567890"
    """Numeric character set
    """

    charset_alphanum = charset_alpha + charset_num
    """Alpha-numeric character set (upper- and lower-case alphabet + numbers)
    """

    charset_all = "".join(chr(x) for x in xrange(0x100))
    """All possible binary characters (``0x0-0xff``)
    """

    charset = charset_alpha
    """The default character set of the ``String`` field class (default=charset_alpha)
    """

    def __init__(self, value=None, **kwargs):
        """Create a new instance of the ``String`` field.

        :param value: The hard-coded value of the String field
        :param int min: The minimum size of the String when built
        :param int max: The maximum size of the String when built
        :param str charset: The character-set to be used when building the string
        """
        super(String, self).__init__(value, **kwargs)

        self.charset = kwargs.setdefault("charset", self.charset)

    def build(self, pre=None):
        """Build the String instance

        :param list pre: The prerequisites list (optional, default=None)
        """
        if pre is None:
            pre = []

        if self.value is not None and rand.maybe():
            return utils.val(self.value, pre)

        length = super(String, self).build(pre)
        res = rand.data(length, self.charset)
        return res

class Join(Field):
    """A ``Field`` subclass that joins other values with a separator.
    This class works nicely with ``Opt`` values.
    """
    
    sep = ","

    def __init__(self, *values, **kwargs):
        """Create a new instance of the ``Join`` class.

        :param list values: The values to join
        :param str sep: The string with which to separate each of the values (default=``","``)
        :param int max: The maximum number of times (inclusive) to build the first item in ``values``.
        This can be useful when a variable number of items in a list is needed. E.g.: ::python
            
            Join(Int, max=5, sep=",")
        """
        self.values = list(values)
        self.sep = kwargs.setdefault("sep", self.sep)
        self.max = kwargs.setdefault("max", None)
    
    def build(self, pre=None):
        """Build the ``Join`` field instance.
        
        :param list pre: The prerequisites list
        """

        if pre is None:
            pre = []

        if self.max is not None:
            # +1 to make it inclusive
            vals = [self.values[0]] * rand.randint(1, self.max+1)
            if len(vals) == 0:
                import pdb
                pdb.set_trace()
        else:
            vals = self.values

        joins = []
        for val in vals:
            try:
                v = utils.val(val, pre)
                joins.append(v)
            except errors.OptGram as e:
                continue
        return self.sep.join(joins)


class And(Field):
    """A ``Field`` subclass that concatenates two values together.
    This class works nicely with ``Opt`` values.
    """

    def __init__(self, *values, **kwargs):
        """Create a new ``And`` field instance.
        
        :param list values: The list of values to be concatenated
        """

        self.values = list(values)
        # to be used internally, is not intended to be set directly by a user
        self.rolling = kwargs.setdefault("rolling", False)
        self.fuzzer = GramFuzzer.instance()
    
    def build(self, pre=None):
        """Build the ``And`` instance

        :param list pre: The prerequisites list
        """
        if pre is None:
            pre = []

        res = deque()
        for x in self.values:
            try:
                res.append(utils.val(x, pre))
            except errors.OptGram as e:
                continue
            except errors.FlushGrams as e:
                prev = "".join(res)
                res.clear()
                # this is assuming a scope was pushed!
                if len(self.fuzzer._scope_stack) == 1:
                    pre.append(prev)
                else:
                    stmts = self.fuzzer._curr_scope.setdefault("prev_append", deque())
                    stmts.extend(pre)
                    stmts.append(prev)
                    pre.clear()
                continue

        return "".join(res)


class Q(And):
    """A ``Field`` subclass that quotes whatever value is provided.
    """

    escape = False
    """Whether or not the quoted data should be escaped (default=``False``). Uses ``repr(X)``
    """

    html_js_escape = False
    """Whether or not the quoted data should be html-javascript escaped (default=``False``)
    """

    quote = '"'
    """Which quote character to use if ``escape`` and ``html_js_escape`` are False (default=``'"'``)
    """

    def __init__(self, *values, **kwargs):
        """Create the new ``Quote`` instance

        :param bool escape: Whether or not quoted data should be escaped (default=``False``)
        :param bool html_js_escape: Whether or not quoted data should be html-javascript escaped (default=``False``)
        :param str quote: The quote character to be used if ``escape`` and ``html_js_escape`` are ``False``
        """
        super(Q, self).__init__(*values, **kwargs)
        self.escape = kwargs.setdefault("escape", self.escape)
        self.html_js_escape = kwargs.setdefault("html_js_escape", self.html_js_escape)
        self.quote = kwargs.setdefault("quote", self.quote)

    def build(self, pre=None):
        """Build the ``Quote`` instance

        :param list pre: The prerequisites list
        """
        res = super(Q, self).build(pre)

        if self.escape:
            return repr(res)
        elif self.html_js_escape:
            return ("'" + res.encode("string_escape").replace("<", "\\x3c").replace(">", "\\x3e") + "'")
        else:
            return "{q}{r}{q}".format(q=self.quote, r=res)


class Or(Field):
    """A ``Field`` subclass that chooses one of the provided values
    at random as the result of a call to the ``build()`` method.
    """

    def __init__(self, *values, **kwargs):
        """Create a new ``Or`` instance with the provide values

        :param list values: The list of values to choose randomly from
        """
        self.values = list(values)
        if "options" in kwargs and len(values) == 0:
            self.values = kwargs["options"]
        self.rolling = kwargs.setdefault("rolling", False)
    
    def build(self, pre=None):
        """Build the ``Or`` instance

        :param list pre: The prerequisites list
        """
        if pre is None:
            pre = []

        return utils.val(rand.choice(self.values), pre)


class Opt(And):
    """A ``Field`` subclass that randomly chooses to either build the
    provided values (acts as an ``And`` in that case), or raise an
    ``errors.OptGram`` exception.

    When an ``errors.OptGram`` exception is raised, the current value being built
    is then skipped
    """

    prob = 0.5
    """The probability of an ``Opt`` instance raising an ``errors.OptGram``
    exception
    """

    def __init__(self, *values, **kwargs):
        """Create a new ``Opt`` instance

        :param list values: The list of values to build (or not)
        :param float prob: A float value between 0 and 1 that defines the probability
        of cancelling the current build.
        """
        super(Opt, self).__init__(*values, **kwargs)
        self.prob = kwargs.setdefault("prob", self.prob)

    def build(self, pre=None):
        """Build the current ``Opt`` instance

        :param list pre: The prerequisites list
        """
        if pre is None:
            pre = []

        if rand.maybe(self.prob):
            raise errors.OptGram

        return super(Opt, self).build(pre)

# ----------------------------
# Non-direct classes
# ----------------------------

class Def(Field):
    """The ``Def`` class is used to define grammar *rules*. A defined rule
    has three parts:

    1. Name - A rule name can be declared multiple times. When a rule name with multiple
    definitions is generated, one of the rule definitions will be chosen at random.

    2. Values - The values of the rule. These will be concatenated (acts the same
    as an ``And``).

    3. Category - Which category to define the rule in. This is an important step and
    guides the fuzzer into choosing the correct rule definitions when randomly choosing
    rules to generate.

    For example, supposed we defined a grammar for various types of postal addresses.
    We could have a grammar for US addresses, UK addresses, and Australian addresses.
    When we want the fuzzer to generate a random address, we would want it to choose
    one from our US, UK, or Australian address rule and not choose to generate only
    a zipcode rule.

    I often have a main ``X`` category, as well as an ``X_def`` category. The ``X``
    category is what I tell to the fuzzer to choose from when randomly generating
    top-level rules. The ``X_def`` category is only used to help build the top-level
    rules.
    """

    sep = ""
    """The separator of values for this rule definition (default=``""``)
    """

    no_prune = False
    """Whether or not this rule should be pruned if the fuzzer cannot find
    a way to reach this rule. (default=``False``)
    """

    def __init__(self, name, *values, **options):
        """Create a new rule definition. Simply instantiating a new rule definition
        will add it to the current ``GramFuzzer`` instance.

        :param str name: The name of the rule being defined
        :param list values: The list of values that define the value of the rule
        (will be concatenated when built)
        :param str cat: The category to create the rule in (default=``"default"``).
        :param bool no_prune: If this rule should not be pruned *EVEN IF* it is found to be
        unreachable (default=``False``)
        """
        self.name = name
        self.options = options
        self.values = list(values)

        self.sep = self.options.setdefault("sep", self.sep)
        self.cat = self.options.setdefault("cat", "default")
        self.no_prune = self.options.setdefault("no_prune", self.no_prune)

        self.fuzzer = GramFuzzer.instance()

        module_name = os.path.basename(inspect.stack()[1][1]).replace(".pyc", "").replace(".py", "")
        self.fuzzer.add_definition(self.cat, self.name, self, no_prune=self.no_prune, gram_file=module_name)
    
    def build(self, pre=None):
        """Build this rule definition
        
        :param list pre: The prerequisites list
        """
        if pre is None:
            pre = []

        res = deque()
        for value in self.values:
            try:
                res.append(utils.val(value, pre))
            except errors.FlushGrams as e:
                prev = "".join(res)
                res.clear()
                # this is assuming a scope was pushed!
                if len(self.fuzzer._scope_stack) == 1:
                    pre.append(prev)
                else:
                    stmts = self.fuzzer._curr_scope.setdefault("prev_append", deque())
                    stmts.extend(pre)
                    stmts.append(prev)
                    pre.clear()
                continue
            except errors.GramFuzzError as e:
                raise errors.GramFuzzError("{} : {}".format(self.name, str(e)))

        return self.sep.join(res)

class Ref(Field):
    """The ``Ref`` class is used to reference defined rules by their name. If a
    rule name is defined multiple times, one will be chosen at random.

    For example, suppose we have a rule that returns an integer: ::python

        Def("integer", UInt)

    We could define another rule that creates a ``Float`` by referencing the
    integer rule twice, and placing a period between them: ::python

        Def("float", Ref("integer"), ".", Ref("integer"))
    """

    def __init__(self, refname, cat="default"):
        """Create a new ``Ref`` instance

        :param str refname: The name of the rule to reference
        :param str cat: The name of the category the rule is defined in
        """
        self.refname = refname
        self.cat = cat

        self.fuzzer = GramFuzzer.instance()
    
    def build(self, pre=None):
        """Build the ``Ref`` instance by fetching the rule from
        the GramFuzzer instance and building it

        :param list pre: The prerequisites list
        """
        if pre is None:
            pre = []

        definition = self.fuzzer.get_ref(self.cat, self.refname)
        return utils.val(definition, pre)
    
    def _get_ref_cls_depth(self, cls=None, count=0):
        if cls is None:
            cls = self.__class__

        if cls is Ref:
            return count

        for base in self.__class__.__bases__:
            return self._get_ref_cls_depth(base, count+1)

        return None
    
    def __repr__(self):
        return "<{}[{}]>".format(self.__class__.__name__, self.refname)
