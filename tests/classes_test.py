# Copyright 2014 Google Inc.117
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for bocado.classes."""

import types
import unittest

from bocado.classes import ArgRef
from bocado.classes import FunctionRef
from bocado.classes import instance_set
from bocado.classes import ParameterizedDict
from bocado.classes import ParameterizedList
from bocado.classes import ParameterizedTuple
from bocado.classes import ParametricType
from bocado.classes import TaggedUnion
from bocado.classes import ValueCollectionDict


class Foo(object):

  def __init__(self):
    self.foo = 1


class InstanceSetTest(unittest.TestCase):

  def test_builtin_type_sample(self):
    tags1 = instance_set([1])
    self.assertEqual(tags1, [int])
    tags2 = instance_set([True])
    self.assertEqual(tags2, [bool])

  def test_instance_sample(self):
    datum1 = Foo()
    datum2 = Foo()
    # Updating the field foo shouldn't change anything
    datum2.foo = 2
    datum3 = Foo()
    # Adding the field bar should change things.
    datum3.bar = "bar"
    self.assertEqual(instance_set([datum1]), [Foo])
    self.assertEqual(instance_set([datum1, datum2]), [Foo])
    self.assertEqual(instance_set([datum1, datum2, datum3]), [Foo, Foo])

class ValueCollectionDictTest(unittest.TestCase):

  def test_list_vcd(self):
    list_vcd = ValueCollectionDict(list)
    list_vcd["a"] = "foo"
    list_vcd["a"] = "bar"
    self.assertEqual(list_vcd["a"], ["foo", "bar"])
    self.assertEqual(len(list_vcd), 1)

  def test_tuple_vcd(self):
    tuple_vcd = ValueCollectionDict(tuple)
    tuple_vcd["a"] = "foo"
    tuple_vcd["a"] = "bar"
    self.assertEqual(tuple_vcd["a"], ("foo", "bar"))
    self.assertEqual(len(tuple_vcd), 1)

  def test_dict_vcd(self):
    dict_vcd = ValueCollectionDict(ValueCollectionDict(list))
    dict_vcd["a"]["b"] = "foo"
    dict_vcd["a"]["b"] = "bar"
    self.assertEqual(dict_vcd["a"]["b"], ["foo", "bar"])

  def test_set_vcd(self):
    set_vcd = ValueCollectionDict(set)
    set_vcd["a"] = "a"
    set_vcd["a"] = "a"
    self.assertEqual(set_vcd["a"], set(["a"]))

class ArgRefTest(unittest.TestCase):

  def setUp(self):
    self.fn = FunctionRef("foo", 1, "fooFn")

  def add_sample(self):
    arg0 = ArgRef(self.fn, "arg0")
    arg0.add_sample(1)
    self.assertEqual(len(arg0.samples), 1)

  def test_get_type(self):
    arg1 = ArgRef(self.fn, "arg1")
    self.assertEqual(arg1.get_type(), types.NoneType)
    arg1.add_sample(1)
    self.assertEqual(arg1.get_type(), int)
    arg1.add_sample(True)
    self.assertEqual(arg1.get_type(), TaggedUnion([int, bool]))
    arg1.add_sample([1, 2, 3])
    expected_type = TaggedUnion([ParameterizedList([int]), int, bool])
    computed_type = arg1.get_type()
    self.assertEqual(computed_type, expected_type)
    # Test the case where we non-equal directories.
    arg2 = ArgRef(self.fn, "arg2")
    arg2.add_sample(Foo())
    self.assertEqual(arg2.get_type(), Foo)
    # Observing another instance of Foo doesn't change the type:
    arg2.add_sample(Foo())
    self.assertEqual(arg2.get_type(), Foo)
    # However, changing Foo's dir should change things
    baz = Foo()
    baz.baz = "asdf"
    arg2.add_sample(baz)
    self.assertNotEqual(arg2.get_type(), Foo)

  def test_get_type_prob(self):
    arg3 = ArgRef(self.fn, "arg3")
    arg3.add_sample(1)
    type_dict = arg3.get_type_prob()
    self.assertEqual(len(type_dict), 1)
    self.assertAlmostEqual(type_dict[int], 1.0)
    arg3.add_sample(True)
    type_dict = arg3.get_type_prob()
    self.assertEqual(len(type_dict), 2)
    self.assertAlmostEqual(type_dict[int], 0.5)
    self.assertAlmostEqual(type_dict[bool], 0.5)


class FunctionRefTest(unittest.TestCase):

  def test_init(self):
    fn1 = FunctionRef("foo", 1, "fooFn")
    fn2 = FunctionRef("foo", 1, "fooFn")
    self.assertEqual(fn1, fn2)
    self.assertIs(fn1, fn2)
    with self.assertRaises(Exception) as e:
      FunctionRef("foo", 1, "foofn")

  def test_get_key(self):
    co1 = compile("print 'foo'", "", "single")
    co2 = compile("print 'foo'", "", "single")
    co3 = compile("print 'bar'", "", "single")
    self.assertEqual(co1, co2)
    self.assertNotEqual(co1, co3)

  def test_get_num_samples(self):
    fn = FunctionRef("bar", 1, "barFn")
    arg1 = ArgRef(fn, "arg1")
    retval = ArgRef(fn, "")
    # Pretend we observed an input, but an exception was thrown.
    arg1.add_sample(True)
    self.assertEqual(fn.get_num_samples(), 1)
    # Observing an output shouldn't change anything
    retval.add_sample("asdf")
    self.assertEqual(fn.get_num_samples(), 1)
    # Observing a successful run should increment by one.
    arg1.add_sample(False)
    retval.add_sample("foo")
    self.assertEqual(fn.get_num_samples(), 2)

  def test_get_return(self):
    fn = FunctionRef("baz", 1, "bazFn")
    argref, returntype = fn.get_return()
    self.assertIsNone(argref)
    self.assertEqual(returntype, types.NoneType)
    retval = ArgRef(fn, "")
    retval.add_sample(1)
    argref, returntype = fn.get_return()
    self.assertIs(argref, ArgRef(fn, ""))
    self.assertIs(returntype, int)

  def test_arity(self):
    # e.g., def square(n):
    #         return n * n
    # arity(square) = 1
    fn = FunctionRef("", 1, "square")
    squarearg = ArgRef(fn, "n")
    self.assertEqual(fn.arity(), 1)

  def test_signaturenature(self):
    import types
    fn = FunctionRef("", -1, "map")
    arg1 = ArgRef(fn, "fn")
    arg2 = ArgRef(fn, "coll")
    retval = ArgRef(fn, "")
    arg1.add_sample(lambda x: x*x)
    arg2.add_sample([1,2,3])
    retval.add_sample([1,4,9])
    fn.set_signaturenature()
    self.assertEqual(fn.signature[""], (-1, ParameterizedList([int])))
    self.assertEqual(fn.signature["fn"], (0, types.FunctionType))
    self.assertEqual(fn.signature["coll"], (1, ParameterizedList([int])))


class ParametricTypeTest(unittest.TestCase):

  def setUp(self):
    ParameterizedList.all_lists = ValueCollectionDict(tuple)
    ParameterizedTuple.all_tuples = ValueCollectionDict(tuple)
    ParameterizedDict.all_dicts = ValueCollectionDict(tuple)
    TaggedUnion.all_unions = ValueCollectionDict(tuple)

  def test_get_collection(self):
    # Instantiating the empty collection does not create a path.
    coll = ParametricType.get_collection([], ParameterizedList.all_lists)
    self.assertIsNone(coll)
    empty = ParameterizedList([])
    coll = ParametricType.get_collection([], ParameterizedList.all_lists)
    self.assertIsNone(coll)
    # Instantiating anything else does.
    coll = ParametricType.get_collection([int], ParameterizedList.all_lists)
    self.assertIsNone(coll)
    intlist = ParameterizedList([int])
    coll = ParametricType.get_collection([int], ParameterizedList.all_lists)
    self.assertIs(coll, intlist)

class ParameterizedTupleTest(unittest.TestCase):

  def test_init(self):
    coll = ParameterizedTuple.all_tuples
    ParametricType.get_collection([bool], coll)
    self.assertIn(bool, coll)
    ParametricType.get_collection([bool, int], coll)
    first_type, second_type = sorted([bool, int], key=lambda t: t.__name__)
    self.assertIn(second_type, coll[first_type][1])
    # Calling `ParameterizedTuple([int])` creates a key for an int tuple.
    ParametricType.get_collection([ParameterizedTuple([int])], coll)
    self.assertIn(ParametricType.get_collection([int], coll), coll)


class ParameteterizedListTest(unittest.TestCase):

  def test_get_list(self):
    coll = ParameterizedList.all_lists
    ParametricType.get_collection([bool], coll)
    self.assertIn(bool, coll)
    ParametricType.get_collection([int], coll)
    self.assertIn(int, coll)
    ParametricType.get_collection([bool, int], coll)
    first_type, second_type = sorted([bool, int], key=lambda t: t.__name__)
    self.assertIn(second_type, coll[first_type][1])
    pl = ParametricType.get_collection([ParameterizedList([bool])], coll)
    # There is now a reified parameterized list of bools that serves as
    # a key, e.g.:
    # { ...
    # <type 'int'>: (
    #   None, {
    #     }),
    # <google3.video.youtube.frontend.utils.python.bocado.classes.ParameterizedList object at 0x1490190>: (
    #   None, {
    #     }),
    # <type 'bool'>: (
    #   <google3.video.youtube.frontend.utils.python.bocado.classes.ParameterizedList object at 0x1490190>, {
    #     <type 'int'>: (
    #       None, {
    #       })})
    # ... }
    self.assertIn(ParametricType.get_collection([bool], coll), coll)

class ParameterizedDictTest(unittest.TestCase):
  # TODO(etosch): No tests exist yet because dictionaries are implemented, but not integrated.

  def test_init(self):
    pass


class TaggedUnionTest(unittest.TestCase):

  def test_init(self):
    union = TaggedUnion([int, bool])
    self.assertEqual(union.tags, [int, bool])
    self.assertIs(union, TaggedUnion([int, bool]))
    # Nested unions are pulled to the top.
    nestedunion = TaggedUnion([TaggedUnion([int, bool]), bool])
    self.assertIs(union, nestedunion)


if __name__ == "__main__":
  unittest.main()
