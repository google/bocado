# Copyright 2014 Google Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import sys
import types
import unittest

from bocado.classes import *
from bocado.output import *
from bocado.value_sampler import *


class Point(object):
  def __init__(self, x, y):
    self.x = x
    self.y = y

def l1_distance(p1, p2):
  return abs(p1.x - p2.x) + abs(p1.y - p2.y)

def newtons_method(n):
  eps = 0.01
  def helper(a, b):
    c = (a + b) / 2.0
    candidate = c * c
    if candidate > n - eps and candidate < n + eps:
      return c
    elif candidate > n:
      return helper(a, c)
    else:
      return helper(c, b)
  return helper(1, n)

def empirical_probabilities(some_list):
  fmap = {}
  n = len(some_list)
  for item in some_list:
    if fmap.has_key(item):
      fmap[item] += 1
    else:
      fmap[item] = 1.0
  # make fmap into pmap
  for k,v in fmap.items():
    fmap[k] = v/n
  return fmap

def ulam(n, steps=0):
  assert n > 0
  if n == 1:
    return steps
  elif (n % 2) == 0:
    return ulam(n / 2, steps + 1)
  else:
    return ulam((3 * n) + 1, steps + 1)

def lambda_in_kwd_args(fn=lambda x: x, args=[]):
  # This function tests function uniqueness by name and line number.
  return fn(args)

def lambda_in_body(args=[]):
  identity = lambda y: y
  return identity(args)

def apply_lambda_immediately(args=(lambda x: x)([])):
  return args

def get_fn(name):
  for filedict in FunctionRef.all_fns.values():
    for fn in filedict.values():
      if fn.funcname == name:
        fn.set_signaturenature()
        return fn


class ValueSamplerTest(unittest.TestCase):

  def setUp(self):
    FunctionRef.all_fns = ValueCollectionDict(dict)
    ArgRef.all_args = ValueCollectionDict(dict)
    self.trace_fn = lambda x, y, z: get_fn_arg_values(x, y, z, skipself=False)

  def test_lambdas(self):
    # Begin tracing.
    sys.settrace(self.trace_fn)
    foo, bar = lambda x: x, lambda y: y
    result0 = foo(bar(1))
    result1 = lambda_in_body(args=123)
    result2 = apply_lambda_immediately(args=321)
    with self.assertRaises(Exception) as e:
      lambda_in_kwd_args()
    # End tracing.
    sys.settrace(None)
    self.assertEqual(foo.__name__, '<lambda>')
    self.assertEqual(bar.__name__, '<lambda>')
    self.assertEqual(result0, 1)
    self.assertEqual(result1, 123)
    self.assertEqual(result2, 321)

  def test_ulam(self):
    # Test a basic recursive function.
    sys.settrace(self.trace_fn)
    ulam(4)
    ulam(5)
    sys.settrace(None)
    # Find Ulam's function in our function dictionary.
    fn = get_fn("ulam")
    self.assertIsNotNone(fn)
    self.assertIs(len(fn.signature), 3)
    self.assertEqual(fn.signature[""][1], int)
    self.assertEqual(fn.signature["n"][1], int)
    self.assertEqual(fn.signature["steps"][1], int)

  def test_local_vars(self):
    # Make sure we aren't picking up any extra variables.
    sys.settrace(self.trace_fn)
    arg = ["foo", "bar", "bar", "baz"]
    empirical_probabilities(arg)
    sys.settrace(None)
    fn = get_fn("empirical_probabilities")
    self.assertIsNotNone(fn)
    self.assertIs(len(fn.signature), 2)
    self.assertEqual(fn.signature[""][1], dict)
    self.assertEqual(fn.signature["some_list"][1], ParameterizedList([str]))

  def test_objects(self):
    sys.settrace(self.trace_fn)
    l1_distance(Point(1,1), Point(2,2))
    sys.settrace(None)
    fn = get_fn("l1_distance")
    self.assertIsNotNone(fn)
    self.assertIs(len(fn.signature), 3)
    self.assertEqual(fn.signature[""][1], int)
    self.assertEqual(fn.signature["p1"][1], Point)
    self.assertEqual(fn.signature["p2"][1], Point)
    # Note that normally we would also use the filename and
    # line number to locate this function.
    init = get_fn("__init__")
    self.assertIsNotNone(init)
    self.assertIs(len(init.signature), 3)
    self.assertEqual(init.signature["self"][1], Point)
    self.assertEqual(init.signature["x"][1], int)
    self.assertEqual(init.signature["y"][1], int)

  def test_nested_defs(self):
    sys.settrace(self.trace_fn)
    newtons_method(9)
    newtons_method(20.25)
    newtons_method(5)
    sys.settrace(None)
    outer_fn = get_fn("newtons_method")
    self.assertIsNotNone(outer_fn)
    self.assertIs(len(outer_fn.signature), 2)
    self.assertEqual(outer_fn.signature[""][1], float)
    self.assertEqual(outer_fn.signature["n"][1], TaggedUnion([float, int]))
    inner_fn = get_fn("helper")
    self.assertIsNotNone(inner_fn)
    # Remember, becuase this is an inner function, helper is actually
    # made into a closure.
    import types
    self.assertIs(len(inner_fn.signature), 6)
    self.assertEqual(inner_fn.signature[""][1], float)
    self.assertEqual(inner_fn.signature["eps"][1], float)
    self.assertEqual(inner_fn.signature["helper"][1], types.FunctionType)
    self.assertEqual(inner_fn.signature["a"][1], TaggedUnion([float, int]))
    self.assertEqual(inner_fn.signature["b"][1], TaggedUnion([float, int]))
    self.assertEqual(inner_fn.signature["n"][1], TaggedUnion([float, int]))


class OutputTest(unittest.TestCase):

  def setUp(self):
    FunctionRef.all_fns = ValueCollectionDict(dict)
    ArgRef.all_args = ValueCollectionDict(dict)
    self.trace_fn = lambda x, y, z: get_fn_arg_values(x, y, z, skipself=False)

  def test_jsonize(self):
    sys.settrace(self.trace_fn)
    ulam(10)
    newtons_method(20.25)
    sys.settrace(None)
    json = serialize(fmt="json")
    # There is only one file.
    self.assertIs(len(json), 1)
    self.assertIn("functions", json[0])
    self.assertIn("filename", json[0])

  def test_tuplize(self):
    sys.settrace(self.trace_fn)
    ulam(10)
    sys.settrace(None)
    tuples = serialize(fmt="table")
    self.assertIs(len(tuples), 3)


if __name__ == "__main__":
  unittest.main()
