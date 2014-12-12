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

"""Defines the top-level tracing function."""
import classes

absorb = lambda x, y, z: None
active = set([])
inactive = set([])
reservoirsize = 100
numsamples = 100

def reset_reservoirsize(n):
  global reservoirsize
  reservoirsize = n

def _add_to_samples(f_code, items):
  """Adds observed values for f_code to samples."""
  fn = classes.FunctionRef(f_code.co_filename,
                   f_code.co_firstlineno,
                   f_code.co_name)
  for k, v in items:
    arg = classes.ArgRef(fn, k)
    arg.add_sample(v)
  return fn


def _stop_sampling(fn):
  # Will want something more clever than this, based on having high confidence
  # in the observed values. We probably want to model this as a DP.
  return all([len(arg.samples) > numsamples for arg in fn.args.values()])


def _inject_listener(frame, fn):
  # Modify runtime bytecode to move the function into the active set if a new
  # type appears.
  pass


def _trace_call(frame, event, arg):
  """The local tracing function for a function call."""
  fn = _add_to_samples(frame.f_code, frame.f_locals.items())
  if _stop_sampling(fn):
    _inject_listener(frame, fn)
    inactive.add(fn.key)
    try:
      active.remove(fn.key)
      # Note: this function is still hanging around in samples, taking up space.
    except KeyError:
      pass
  # _trace_call's return function is called on every subsequent event in scope.
  return _trace_return


def _trace_exception(frame, event, arg):
  return None


def _trace_return(frame, event, arg):
  # arg is not None only for returns and exceptions.
  if arg is not None:
    if type(arg) is tuple and len(arg) == 3:
      return _trace_exception
    # Otherwise, we are a return event.
    _add_to_samples(frame.f_code, [("", arg)])


def get_fn_arg_values(frame, event, arg, skipself=True):
  """The top-level tracing function.
  Call sys.settrace(value_sampler.get_fn_arg_values) to
  start your trace from another program."""
  # According to the docs, the top-level tracing function
  # is only ever called for the "call" event. This function
  # should never be used as a return value of a trace.
  assert event == "call", "Top-level event is %s" % event
  if skipself:
    if "bocado" in frame.f_code.co_filename:
      return None
  key = classes.FunctionRef.get_key(frame.f_code)
  if key in active:
    return _trace_call
  elif key in inactive or len(active) >= reservoirsize:
    return None
  else:
    active.add(key)
    return _trace_call
