# interpol.py
A simple, single-file module for providing interpolation with locals support to Python.

Evaluated parts of the string are passed to eval, local variables are inferred from parent's local scope where possible.

Local inference may not work on all python implementations due to the usage of the call stack, should work with CPython at the very least.

The inferred locals are only those available from the call stack and so likely won't support closure captures etc, you will likely have to alias those into the scope first.

### Usage
```python
from interpol import interpolate

# You can use interpolate as a function.
name = "world"
print(interpolate("Hello %{name}."))

# You can also use it on the right-hand of any division with a string.
print("Hello %{name}."/interpolate)

# This is typically better looking when a shorter name is used:
i = interpolate
print("Hello %{name}."/i)

# You can pass locals / globals in with this syntax too:
print("Hello %{name}."/interpolate({"name": "also world"}))
print("Hello %{name}."/interpolate(locals={"name": "also world"}))

# You can explicitly provide locals either by their placement ([string, ]locals, globals) or as keyword arguments:
interpolate(..., locals={...})
"string"/interpolate({...})
interpolate("string", {locals}, {globals})
# etc

# If you intend to use the same interpolation many times it may be a good idea to use the compile method:
compiled = interpolate.compile("Hello %{name}")
print(compiled.interpolate())
print(compiled.interpolate({"name": "also world"})

# You can escape the interpolation syntax by doubling the %%:
print("%%{hello}"/i)
```

### Performance
Due to being implemented in pure python and having to compile and evaluate python code the performance is far below that of format. I therefore don't recommend using this if performance is key at all. Here are some timeit benchmarks:
```python
1,000 'Test %{a}', no pre-compile time time: 0.02390389097854495
1,000 'Test %{a}', no pre-compile time time: 0.022459194995462894
1,000 'Test %{a}', no pre-compile time time: 0.022449620999395847
1,000 'Test %{a} and %{a} and %{a}', no pre-compile time: 0.04242120310664177
1,000 'Test %{a} and %{a} and %{a}', no pre-compile time: 0.03899335814639926
1,000 'Test %{a} and %{a} and %{a}', no pre-compile time: 0.03977311588823795
1,000 'Test %{a and a and a and a and 'Hello World' == 'Hello World'}', no pre-compile time: 0.06429069815203547
1,000 'Test %{a and a and a and a and 'Hello World' == 'Hello World'}', no pre-compile time: 0.06474802596494555
1,000 'Test %{a and a and a and a and 'Hello World' == 'Hello World'}', no pre-compile time: 0.06646277289837599
1,000 precompiled 'Test %{a}' time: 0.008587033953517675
1,000 precompiled 'Test %{a}' time: 0.008428404107689857
1,000 precompiled 'Test %{a}' time: 0.008313735015690327
1,000 precompiled 'Test %{a} and %{a} and %{a}' time: 0.01043956633657217
1,000 precompiled 'Test %{a} and %{a} and %{a}' time: 0.010035686660557985
1,000 precompiled 'Test %{a} and %{a} and %{a}' time: 0.010169623885303736
1,000 'Test {} {} {}' with .format time: 0.0004477649927139282
1,000 'Test {} {} {}' with .format time: 0.0004347860813140869
1,000 'Test {} {} {}' with .format time: 0.0004571452736854553
```