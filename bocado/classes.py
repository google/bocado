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

"""Classes used by the sampler."""

import sys
import types


def instance_set(samples):
  unique_classes = []
  dirs_by_class = ValueCollectionDict(set)
  type_set = set()
  for sample in samples:
    class_or_type = type(sample)
    if class_or_type is list:
      type_set.add(ParameterizedList(instance_set(sample)))
    elif class_or_type is tuple:
      type_set.add(ParameterizedTuple(instance_set(sample)))
    else:
      dir_tuple = tuple(sorted(dir(sample)))
      if (sample.__class__ not in dirs_by_class or
          dir_tuple not in dirs_by_class[sample.__class__]):
        dirs_by_class[sample.__class__] = dir_tuple
        unique_classes.append(class_or_type)
  return unique_classes + list(type_set)


class ValueCollectionDict(dict):
  """Dictionary whose values are collections."""
  # Automatically adds the appropriate collection type if the value is not
  # currently instantiated. Setter doesn't replace; it appends. The test
  # file illustrates behavior.

  def __init__(self, collectiontype):
    self.collectiontype = collectiontype
    super(ValueCollectionDict, self).__init__()

  def __setitem__(self, key, value):
    key_present = self.has_key(key) and self[key] is not None

    if self.collectiontype == list and key_present:
      super(ValueCollectionDict, self).__getitem__(key).append(value)

    elif self.collectiontype == list and not key_present:
      super(ValueCollectionDict, self).__setitem__(key, [value])

    elif self.collectiontype == set and key_present:
      super(ValueCollectionDict, self).__getitem__(key).add(value)

    elif self.collectiontype == set and not key_present:
      super(ValueCollectionDict, self).__setitem__(key, set([value]))

    elif self.collectiontype == tuple and key_present:
      newlist = list(self[key])
      newlist.append(value)
      super(ValueCollectionDict, self).__setitem__(key, tuple(newlist))

    elif self.collectiontype == tuple and not key_present:
      super(ValueCollectionDict, self).__setitem__(key, (value,))

    elif isinstance(self.collectiontype, ValueCollectionDict):
      if isinstance(value, ValueCollectionDict):
        super(ValueCollectionDict, self).__setitem__(key, value)
      else:
        return lambda z: self[key].__setitem__(value, z)

    else:
      raise Exception("Unsupported collection type: %s" % self.collectiontype)

  def __getitem__(self, key):
    if not self.has_key(key):
      if isinstance(self.collectiontype, ValueCollectionDict):
        self[key] = ValueCollectionDict(self.collectiontype.collectiontype)
      else:
        super(ValueCollectionDict, self).__setitem__(key, self.collectiontype())
    return super(ValueCollectionDict, self).__getitem__(key)

  def replace_value(self, key, value):
    super(ValueCollectionDict, self).__setitem__(key, value)

# end ValueCollectionDict


class ArgRef(object):
  """Argument container."""

  all_args = ValueCollectionDict(dict)

  def __new__(cls, owner, argname):
    if owner in ArgRef.all_args and argname in ArgRef.all_args[owner]:
      return ArgRef.all_args[owner][argname]
    retval = super(ArgRef, cls).__new__(cls, owner, argname)
    retval._init = False
    return retval

  def __init__(self, owner, argname):
    if self._init:
        return
    self.owner = owner
    self.argname = argname
    if argname:
      self.position = owner.arity()
    else:
      self.position = -1
    self.samples = []
    self.key = hash((self.owner.funcname, self.argname, self.position))
    owner.args[self.key] = self
    ArgRef.all_args[owner][argname] = self
    self._init = True

  def __repr__(self):
    return "ArgRef(%s, %s, %d)@%d" % (self.owner.__repr__(),
                                      self.argname,
                                      self.position,
                                      id(self)
                                      )

  def get_type(self):
    if not self.samples:
      return types.NoneType
    else:
      first_type = type(self.samples[0])
      tags = instance_set(self.samples)
      if len(tags) == 0:
        raise Exception("No types inferred for %d samples." % len(self.samples))
      elif len(tags) == 1:
        return tags[0]
      else:
        return TaggedUnion(tags)

  def get_type_prob(self):
    sample_types = instance_set(self.samples)
    n = float(len(sample_types))
    type_dict = {}
    for sample_type in sample_types:
      if sample_type in type_dict:
        type_dict[sample_type] += 1
      else:
        type_dict[sample_type] = 1
    for k, v in type_dict.items():
      type_dict[k] = v/n
    return type_dict

  def add_sample(self, sample):
    self.samples.append(sample)

# class ArgRef


class FunctionRef(object):
  """Container for Function information."""

  all_fns = ValueCollectionDict(dict)

  def __new__(cls, filename, lineno, funcname, method=False):
    if (filename in FunctionRef.all_fns
        and lineno in FunctionRef.all_fns[filename]):
      return FunctionRef.all_fns[filename][lineno]
    retval = super(FunctionRef, cls).__new__(cls, filename, lineno, funcname, method=False)
    retval._init = True
    return retval

  def __init__(self, filename, lineno, funcname, method=False):
    if (filename in FunctionRef.all_fns
        and lineno in FunctionRef.all_fns[filename]):
      if funcname != self.funcname:
        raise Exception(
            "Cannot have two functions in the same file (%s) with the "
            "same line number (%d), but different names (%s vs. %s)." %
            (filename, lineno, funcname, self.funcname))
      return
    if not self._init:
      return
    self.filename = filename
    self.lineno = lineno
    self.funcname = funcname
    self.method = method
    self.args = {}
    # string of argname |-> tuple of position * type
    self.signature = {}
    self.key = self.__hash__()
    FunctionRef.all_fns[filename][lineno] = self
    self._init = False

  def __hash__(self):
    return hash((self.filename, self.funcname, self.lineno))

  def __repr__(self):
    return "FunctionRef(%s, %d, %s, method=%s)@%d" % (self.filename,
                                                      self.lineno,
                                                      self.funcname,
                                                      self.method,
                                                      id(self)
                                                      )

  @staticmethod
  def get_key(f_code):
    """Returns a unique identifier for the function in f_code."""
    # f_code is a structure containing code information in a stack frame.
    # The first argument to the trace function is a frame. f_code is a
    # field on this frame.
    return hash((f_code.co_filename, f_code.co_name, f_code.co_firstlineno))

  def get_num_samples(self):
    """Returns the maximum number of samples observed for any of this function's arguments."""
    # When would the number of samples be different for the different arguments?
    # When we are interrupted by an exception. Not sure how we want to handle
    # that. For now, exclude return values from calculating the number of
    # samples.
    # Solution: use max instead; we also seem to have a problem with generators.
    samples = [arg.samples for arg in self.args.values() if arg.position != -1]
    if not samples:
      return 0
    num_samples = len(samples[0])
    for sample in samples[1:]:
      num_samples = max(len(sample), num_samples)
    return num_samples

  def get_return(self):
    """Returns a 2-tuple consisting of the return type.
    The first argument is the ArgRef object or None.
    The second is the inferred type."""
    for arg in self.args.values():
      if arg.argname == "" and arg.position == -1:
        return arg, arg.get_type()
    else:
      return None, types.NoneType

  def arity(self):
    # Arity is a function that that returns the number of arguments
    # to a function.
    # arity(arity) = 1
    # arity(math.pow) = 2
    return len(self.args)

  def get_sorted_arg_list(self):
    return sorted(self.args.values(), key=lambda arg: arg.position)

  def set_signature(self):
    args = self.get_sorted_arg_list()
    for arg in args:
      self.signature[arg.argname] = (arg.position, arg.get_type())

# class FunctionRef


class ParametricType(object):
  """Base class for Lists and Tuples."""

  parametric_types = set([list, tuple, dict])

  @staticmethod
  def get_collection(tags, all_collection):
    # We are simulating a trie in all_collection.
    # Keys are types and values are 2-tuples of the collection type and
    # the nested lookup.
    # This does not create the collection type; it only returns the
    # instance if it exists and creates the path structure if it doesn't.
    # Need a container so we can reset this value.
    accumulator = [all_collection]
    maybe_my_coll = None
    for tag in tags:
      maybe_my_coll, new_accumulator = accumulator[0][tag] or (None, None)
      if new_accumulator:
        accumulator[0] = new_accumulator
      else:
        newer_accumulator = ValueCollectionDict(tuple)
        accumulator[0].replace_value(tag, (maybe_my_coll, newer_accumulator))
        accumulator[0] = newer_accumulator
    return maybe_my_coll

  @staticmethod
  def make_and_store_parametric_coll(cls, clstype, coll, tags):
    # If I'm calling this it's because the correct PL doesn't exist.
    if not tags:
      if hasattr(clstype, "emptytype"):
        return clstype.emptytype
      else:
        raise Exception("All collection types must have an `emptytype` field.")
    accumulator = [coll]
    last_accumulator = None
    for tag in tags:
      # Zip down to the end.
      last_accumulator = accumulator[0]
      _, new_accumulator = accumulator[0][tag]
      accumulator[0] = new_accumulator
    # Get the last accumulator at the last tag -- this will be where we want to store the list.
    retval = super(clstype, cls).__new__(cls, tags)
    if last_accumulator:
      last_accumulator.replace_value(tag, (retval, new_accumulator))
    # Tag this object so we know init should be called as usual.
    retval._init = False
    return retval

  def to_string(self, name, tag_set):
    def write_prod(tag_set):
      string = ""
      for tag in list(tag_set)[:-1]:
        string = "%s %s *" % (string, tag.__name__)
      string = "%s %s" % (string, list(tag_set)[-1].__name__)
      return string + " "
    if tag_set:
      if isinstance(self, ParameterizedDict):
        string1 = write_prod(self.keytags)
        string2 = write_prod(self.valuetags)
        return "%s of (%s |-> %s)" % (name, string1, string2)
      else:
        return "%s of (%s)" % (name, write_prod(tag_set))
    else:
      return "%s of ()" % name

  def __str__(self):
    return self.__name__

# class ParametricType


class EmptyType(ParametricType):

  def __init__(self, name):
    self.__name__ = "%s of ()" % name
    self.tags = None


class ParameterizedTuple(ParametricType):
  """The type variable for a tuple of other types."""

  all_tuples = ValueCollectionDict(tuple)
  emptytype = EmptyType("Tuple")

  def __new__(cls, tags):
    maybe_my_tuple = ParametricType.get_collection(tags, ParameterizedTuple.all_tuples)
    return maybe_my_tuple or ParametricType.make_and_store_parametric_coll(
        cls, ParameterizedTuple, ParameterizedTuple.all_tuples, tags)

  def __init__(self, tags):
    if self._init:
      return
    if type(tags) is tuple:
      self.tags = tags
    elif type(tags) is list:
      self.tags = tuple(tags)
    else:
      raise Exception(
          "Tags must be tuple or list, not %s (Order matters)." %
          type(tags))
    self.__name__ = self.to_string("Tuple", self.tags)

  def __hash__(self):
    tupe = []
    for tag in self.tags:
      if isinstance(tag, ParametricType):
        tupe.append(tag.__class__)
      else:
        tupe.append(tag)
    return hash(tuple(tupe))

  def __repr__(self):
    return "%s@%d" % (self.__name__, id(self))

# class ParameterizedTuple


class ParameterizedList(ParametricType):
  """The type variable for a list of other types."""

  all_lists = ValueCollectionDict(tuple)
  emptytype = EmptyType("List")

  def __new__(cls, tags):
    assert len(tags) == len(set(tags)), "Lists are unordered and should not contain multiples."
    # Sort so our order is deterministic.
    sorted_tags = sorted(tags, key=lambda t: t.__name__)
    maybe_my_list = ParametricType.get_collection(sorted_tags, ParameterizedList.all_lists)
    return maybe_my_list or ParametricType.make_and_store_parametric_coll(
      cls, ParameterizedList, ParameterizedList.all_lists, sorted_tags)

  def __init__(self, tags):
    if self._init:
      return
    self.tags = tuple(tags)
    if len(tags) == 0:
      self.__name__ = list.__name__
    if len(tags) == 1:
      self.__name__ = self.to_string("List", self.tags)
    else:
      self.__name__ = self.to_string("List", [TaggedUnion(self.tags)])

  def __repr__(self):
    return "%s@%d" % (self.__name__, id(self))

#  ParameterizedList


class ParameterizedDict(ParametricType):
  """ The type variable associated with dictionaries."""

  all_dicts = ValueCollectionDict(tuple)
  emptytype = EmptyType("Dict")

  def __new__(cls, keytags, valuetags):
    # Assumes that any of the key tags may be matched with any of the value tags.
    sorted_keytags = sorted(set(keytags), key=lambda t: t.__name__)
    sorted_valuetags = sorted(set(valuetags), key=lambda t: t.__name__)
    tags = sorted_keytags + sorted_valuetags
    maybe_my_dict = ParametricType.get_collection(
      tags, ParameterizedDict.all_dicts)
    return maybe_my_dict or ParametricType.make_and_store_parametric_coll(
      cls, ParameterizedDict, ParameterizedDict.all_dicts, tags)

  def __init__(self, keytags, valuetags):
    if self._init:
      return
    self.keytags = keytags
    self.valuetags = valuetags
    self.__name__ = to_string(self, "Dict", set(keytags, valuetags))

  def __repr__(self):
    return "%s@%d" % (self.__name__, id(self))

# ParameterizedDict


class TaggedUnion(ParametricType):
  """The type variable for a union of other types."""

  all_unions = ValueCollectionDict(tuple)

  @staticmethod
  def _propagate_unions(tags):
    # A union containing a union needs to be flattened.
    for tag in tags:
      if isinstance(tag, TaggedUnion):
        tags.remove(tag)
        for descendent_tag in tag.tags:
          if descendent_tag not in tags:
            tags.append(descendent_tag)

  def __new__(cls, tags):
    # Tags may not be distinct, but they will be made distinct in
    # the init function.
    TaggedUnion._propagate_unions(tags)
    sorted_tags = sorted(set(tags), key=lambda t: t.__name__)
    maybe_my_union = ParametricType.get_collection(sorted_tags, TaggedUnion.all_unions)
    return maybe_my_union or ParametricType.make_and_store_parametric_coll(
      cls, TaggedUnion, TaggedUnion.all_unions, sorted_tags)

  def __init__(self, tags):
    if self._init:
      return
    self.tags = sorted(tags)
    # It is the responsibility of the creator to ensure that repetitions in union
    # tags actually represent different types.
    self.__name__ = self.to_string("Union", self.tags)

  def __repr__(self):
    return "%s@%d" % (self.__name__, id(self))

#  TaggedUnion
