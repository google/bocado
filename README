About
=====
This package is the result of an intern project in Fall 2014. It implements a sampling procedure to collect types of Python function arguments and return values.

Usage
=====
Add the following lines to import:

`import sys`
`from bocado import classes`
`from bocaod import value_sampler`

Then begin sampling with:

`sys.settrace(value_sampler.get_fn_arg_values)`

If you would like to stop tracing, call:

`sys.settrace(None)`

The output module contains functions and procedures for returning and/or dumping data. For example:

```
from bocado import output
with file('type_output.txt', 'a') as f:
  output.pretty_print_types(stream=f)
```

Install
=======
Clone this repository and run `python setup.py install`.

Licence
=======
Apache 2.0

Author
=====
etosch