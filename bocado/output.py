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
"""This module contains functions for sending data to other sources."""
from operator import attrgetter
import sys

from classes import TaggedUnion, FunctionRef
from value_sampler import inactive

# Strings used as keys, interned for fast lookup (supposedly).
# I want these things to behave like symbols.
_filename = "filename"
_functions = "functions"
_lineno = "lineno"
_name = "name"
_arguments = "arguments"
_types = "types"
_empirical_probability = "empirical_probability"
_table = "table"
_json = "json"
_proto = "proto"
_id = "id"
intern(_filename)
intern(_functions)
intern(_lineno)
intern(_name)
intern(_arguments)
intern(_types)
intern(_empirical_probability)
intern(_table)
intern(_json)
intern(_proto)


def print_csv(stream=sys.stdout, printheader=True):
  """Prints out the serialized version of our type samples as a csv."""
  if stream.closed:
    raise Exception("Stream is closed; management must be performed by the "
                    "caller.")
  tuples = serialize(fmt="table")
  if printheader:
    headerline = ",".join([k for k, v in serialize.headers])
    stream.write("%s\n" % headerline)
  for tupe in tuples:
    stream.write("%s\n" % ",".join([str(t) for t in tupe]))
  stream.flush()

def pretty_print_types(stream=sys.stdout, onlycompleted=False, repeat=False):
  """Prints out type information for functions to an output stream."""
  # """
  # Prints out the function name, its return value, and each of the argument
  # names, their types, and the empirical probability of seeing that type.
  # Opening and closing the target print location should be managed by the
  # caller.

  # :param samples: The lookup table of samples. Values should be of type
  # `FunctionRef`.
  # :param stream: The location to print to.
  # """
  if stream.closed:
    raise Exception("Stream is closed; management must be performed by the "
                    "caller.")

  samples = [v for other_dict in FunctionRef.all_fns.values() for v in other_dict.values()]
  if onlycompleted:
    for sample in samples:
      if sample.key not in inactive:
        samples.remove(sample)

  if not hasattr(pretty_print_types, "num_samples"):
    pretty_print_types.num_samples = {}

  def _progress(f):
    samples_new = f.get_num_samples()
    if f.key in pretty_print_types.num_samples:
      samples_old = pretty_print_types.num_samples[f.key]
      if samples_new == samples_old:
        return False
    pretty_print_types.num_samples[f.key] = samples_new
    return True

  def _strunion(arg, v):
    if isinstance(v, TaggedUnion):
      types = arg.get_type_prob().items()
      unions = ["\n\t\t%s (%0.2f)" % (t.__name__, prob) for t, prob in types]
      return "".join(unions)
    else:
      return ""

  # Print stuff.
  for f in samples:

    if onlycompleted and f.key not in inactive:
      continue

    f.set_signature()
    if not repeat and not _progress(f):
      continue

    strsig = [""]*(len(f.args) + 1)
    returnarg, returntype = f.get_return()
    strsig[0] = "\n\n%s:%d@%d\n%s returns %s%s" % (
        f.filename, f.lineno, id(pretty_print_types.num_samples),
        f.funcname, returntype.__name__,
        _strunion(returnarg, returntype))

    for arg, (i, v) in [(arg, f.signature[arg.argname]) for arg in f.args.values()]:
      if i == -1:
        continue
      try:
        unique_ct = len(set(arg.samples))
      except TypeError:
        unique_ct = -1
      except AttributeError:
        # TODO(etosch): This is a hack to run okay for LGeoInfo
        unique_ct = -2
      strsig[i+1] = "\n\t(%d) %s : %s\t (#/samples: %d, #/distinct: %d)%s" % (
          i, arg.argname, v.__name__, len(arg.samples), unique_ct,
          _strunion(arg, v))
    stream.write("".join(strsig))
    stream.flush()



def _protoize(samples):
  pass


def _jsonize(container, filename, lineno, funcname, argname, argtype, typeprob, functionmem):
  # Wanted to use ValueCollectionDict here, but that doesn't work with the
  # schema.
  module = [m for m in container if m[_filename] == filename]
  fn = module and [f for f in module[0][_functions] if f[_lineno] == lineno]
  assert (not fn) or fn[0][_name] == funcname, (
      "Function %s and function %s both found at line %d" % (
          fn[0][_name], funcname, lineno))
  arg = fn and [a for a in fn[0][_arguments] if a[_name] == argname]
  tt = arg and [t for t in arg[0][_types] if t[_name] == argtype]
  if tt:
    # Just replace type probability.
    tt[0][_empirical_probability] = typeprob
  elif arg:
    # If the type wasn't found, add it.
    arg[0][_types].append({
        _name: argtype,
        _empirical_probability: typeprob
        })
  elif fn:
    # If the argument wasn't found, add it.
    fn[0][_arguments].append({
        _name: argname,
        _id: functionmem,
        _types: [{
            _name: argtype,
            _empirical_probability: typeprob
            }]
        })
  elif module:
    # If the function wasn't found, add it.
    module[0][_functions].append({
        _lineno: lineno,
        _name: funcname,
        _arguments: [{
            _name: argname,
            _types: [{
                _name: argtype,
                _empirical_probability: typeprob
                }]
            }]
        })
  else:
    # If the module wasn't found, add it.
    container.append({
        _filename: filename,
        _functions: [{
            _lineno: lineno,
            _name: funcname,
            _arguments: [{
                _name: argname,
                _types: [{
                    _name: argtype,
                    _empirical_probability: typeprob
                    }]
                }]
            }]
        })


def _tuplize(container, filename, lineno, funcname, argname, argtype, typeprob, functionmem):
  container.append((filename, lineno, funcname, argname, argtype, typeprob, functionmem))


def serialize(fmt=_table):
  """Serializes type information for use elsewhere (e.g., an IDE)."""
  # """
  # Serializes type information for use elsewhere (e.g., an IDE).
  # one of "table", "proto", or "json".

  # fmt="table"
  # =============
  # Produces a list of tuples, modelling a table.
  # Serialize has "headers" property, which provides column names and types for
  # a database or csv. It is a list of 2-tuples, accessible via
  # `serialize.headers`.

  # fmt="json"
  # ============
  # Produces a dictionary on which json.dumps can be called. Should conform to
  # the schema specified in schemata/type_info.json

  # fmt="proto"
  # =============
  # Produces a python object that conforms to the protocol buffer defined in
  #  protos/type_info.proto.

  # :param samples: A dictionary of samples, defined using the `FunctionRef`.
  # :param fmt: One of "table", "proto",  or "json".
  # :return: A list of tuples.
  # """
  if not hasattr(serialize, "headers"):
    serialize.headers = ((_filename, str), (_lineno, int), ("funcname", str),
                         ("argname", str), ("argtype", str), ("typeprob", float),
                         ("id", int))
  # Make some container that we can pass as a reference
  generic_return_value = []
  samples = FunctionRef.all_fns
  for filename, innerdict in samples.items():
    for lineno, func in innerdict.items():
      funcname = func.funcname
      functionmem = id(func)
      for arg in func.args.values():
        argname = arg.argname
        argtypes = arg.get_type_prob()
        for argtype, typeprob in argtypes.items():
          if fmt is _table:
            _tuplize(generic_return_value,
                     filename, lineno, funcname, argname, argtype, typeprob, functionmem)
          elif fmt is _json:
            _jsonize(generic_return_value,
                     filename, lineno, funcname, argname, argtype, typeprob, functionmem)
          elif fmt is _proto:
            assert False, "PROTO NOT YET IMPLEMENTED"
          else:
            raise Exception("Unknown serialization format: %s" % fmt)
  return generic_return_value


def store(samples):
  pass
