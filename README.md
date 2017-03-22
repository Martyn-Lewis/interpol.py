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