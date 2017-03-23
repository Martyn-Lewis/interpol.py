import re

# Detect stack frame traversal support as some Python implementations don't support it. CPython should.
def detect_inspection_support(seek_target):
    try:
        import inspect
        frame = inspect.currentframe()
        parent = frame.f_back
        local = parent.f_locals
        return seek_target in local
    except (ImportError, AttributeError):
        return False

test_target = 100
supports_stack_inspection = detect_inspection_support('test_target')
del test_target

if supports_stack_inspection:
    import inspect


# Basic errors
class InterpolationError(Exception):
    pass


class InterpolatorCompilerError(InterpolationError):
    pass


class Interpolator(object):
    variable = re.compile(r'^[a-z_][a-z0-9_]*$', re.IGNORECASE)

    def __init__(self, _locals=None, _globals=None):
        self.locals = _locals
        self.globals = _globals

    @staticmethod
    def _scope_out_locals(depth):
        frame = inspect.currentframe()
        parent = frame
        for x in range(depth):
            parent = parent.f_back
        _locals = parent.f_locals
        return _locals

    @staticmethod
    def _prepare_args(_locals, _globals, args, kwargs, depth):
        _target = None

        # Derive scope from keyword arguments if provided.
        if 'locals' in kwargs:
            _locals = kwargs['locals']
        if 'globals' in kwargs:
            _globals = kwargs['globals']

        # Derive scope from arguments if provided.
        args = list(args)
        if len(args) and type(args[0]) is str:  # (target, ...)
            _target = args[0]
            del args[0]

        if len(args):  # (target, locals, ...)
            _locals = args[0]
            del args[0]

        if len(args):  # (target, locals, globals)
            _globals = args[0]

        if supports_stack_inspection and _locals is None:
            _locals = Interpolator._scope_out_locals(depth + 1)

        if _locals is None:
            _locals = {}

        if _globals is None:
            _globals = globals()

        return  _target, _locals, _globals

    def __call__(self, *args, **kwargs):
        if not len(args) and not len(kwargs):
            return self

        _locals = self.locals
        _globals = self.globals

        _target, _locals, _globals = self._prepare_args(_locals, _globals, args, kwargs, 2)

        if _target is None:
            # Defer an interpolator for later use.
            return Interpolator(_locals, _globals)
        else:
            return Interpolator(_locals, _globals)._interpolate(_target)

    def __rtruediv__(self, other):
        if not type(other) is str:
            raise TypeError("Attempted to infer interpolation with a non-string type, has your precedence been muddled? Check any x/interpolate")

        if self is interpolate:
            _locals = {}
            if supports_stack_inspection:
                _locals = Interpolator._scope_out_locals(2)

            return Interpolator(_locals)._interpolate(other)
        else:
            return self._interpolate(other)

    def _interpolate(self, target):
        _locals = self.locals or {}
        _globals = self.globals or globals()

        return self.compile(target).interpolate(_locals, _globals)

    def compile(self, string):
        _variable_match = Interpolator.variable
        _offset = 0

        compiled = CompiledInterpolator()

        # This needs to be broken up for better parsing at some point.
        # Currently it's just testing "does this work?" and "how practical is this?"
        while True:
            start = string.find('%{', _offset)
            if start == -1:
                break

            # Due to a weird catastrophic backtracking that only occurs in Python's re, we check for escaping here instead.
            if start > 0 and string[start - 1: start + 1] == '%%':
                compiled.add_component(StringInterpolatorComponent(string[_offset: start - 1] + "%{"))
                _offset = start + 2
                continue

            # Make sure we capture the text in between.
            compiled.add_component(StringInterpolatorComponent(string[_offset:start].replace('%%{', '%{')))

            # We need to safely guarantee the behaviour of strings and dictionaries inside our expression.
            # Consider:
            #   %{"Hello there }"}
            #       - should properly end at the final }, not the } inside the string.
            #   %{{"a": 123}["a"]}
            #       - should properly end at the final }, not the dictionary's }.
            #   %{"sub interpolation %{\\\"just to confuse the hell out of you\\\"}"/interpolate}
            #       - should properly induce headaches.
            seek_from = start + 2
            seek = 0
            in_string = False
            brace_counter = 0
            while seek_from + seek < len(string):
                offset = seek_from + seek

                # Substring checks.
                if in_string:
                    if string[offset] == '\\':
                        # Skip both the backslash and whatever it escapes
                        if string[offset + 1] == 'x':
                            seek += 4
                        else:
                            seek += 2
                        continue
                    elif string[offset] == in_string:
                        in_string = False
                        seek += 1
                        continue
                    else:
                        seek += 1
                        continue
                elif string[offset] in ['"', "'"]:
                    in_string = string[offset]
                    seek += 1
                    continue

                if string[offset] == '}':
                    seek += 1
                    if brace_counter > 0:
                        if seek_from + seek + 1 < len(string):
                            # Don't decrease the counter when we're actually hanging.
                            # Kind of a hacky way of doing this.
                            brace_counter -= 1
                        continue
                    else:
                        # We've finally escaped.
                        break

                if string[offset] == '{':
                    brace_counter += 1

                seek += 1
                continue
            if seek_from + seek >= len(string) and (string[-1] != '}' or brace_counter > 0):
                raise InterpolatorCompilerError("seemingly unclosed interpolation braces from offset {}".format(seek_from))

            evaluation = string[seek_from: seek_from + seek - 1].strip()
            if _variable_match.match(evaluation):
                compiled.add_component(VariableInterpolatorComponent(evaluation))
            else:
                compiled.add_component(EvaluationInterpolatorComponent(evaluation))
            _offset = seek_from + seek

        tail = string[_offset:].replace('%%{', '%{')
        if len(tail):
            compiled.add_component(StringInterpolatorComponent(tail))
        return compiled


class CompiledInterpolator(object):
    def __init__(self):
        self.components = []

    def add_component(self, component):
        self.components.append(component)

    def interpolate(self, *args, **kwargs):
        # Fairly hacky way to do this; we prepend an empty string to the args so that there is no target.
        # This guarantees that the behaviour of our arguments and scope meets that of the Interpolator, however.
        _target, _locals, _globals = Interpolator._prepare_args(None, None, [''] + list(args), kwargs, 2)
        return "".join(x.interpolate(_locals, _globals) for x in self.components)


class BaseInterpolatorComponent(object):
    def interpolate(self, locals, globals):
        raise NotImplementedError("Derivitive of BaseInterpolatorComponent did not implement interpolate")


class StringInterpolatorComponent(BaseInterpolatorComponent):
    def __init__(self, string):
        self.value = string

    def interpolate(self, locals, globals):
        return self.value


class EvaluationInterpolatorComponent(BaseInterpolatorComponent):
    def __init__(self, string):
        self.debug = string
        try:
            self.value = compile(string, '', 'eval')
        except Exception as ex:
            raise InterpolatorCompilerError("error occurred while trying to compile interpolation code for '{}': {}".format(string, str(ex)))

    def interpolate(self, locals, globals):
        try:
            return str(eval(self.value, globals, locals))
        except Exception as ex:
            raise InterpolationError("error occurred while trying to evaluate fragment '{}': {}".format(self.debug, str(ex)))


class VariableInterpolatorComponent(BaseInterpolatorComponent):
    def __init__(self, string):
        self.key = string

    def interpolate(self, locals, globals):
        key = self.key

        if key in locals:
            return str(locals[key])

        if key in globals:
            return str(globals[key])

        raise InterpolationError("tried to interpolate variable {}, but it's not in any scope".format(key))

interpolate = Interpolator()

if __name__ == "__main__":
    # Tests

    # Accidental destruction tests.
    assert ("Test"/interpolate == "Test")
    assert ("Test 2"/interpolate == "Test 2")

    # Basic interpolation tests with local inference.
    a = 123
    assert ("Test %{a}"/interpolate == "Test 123")
    assert ("Test %{a * 2}"/interpolate == "Test 246")
    assert ("Test %{100 if a == 123 else 200}"/interpolate == "Test 100")

    # Manual scope interpolation tests.
    scope = {'a': 321}
    assert ("Test %{a}"/interpolate(scope) == "Test 321")
    assert ("Test %{a * 2}"/interpolate(scope) == "Test 642")
    assert ("Test %{100 if a == 123 else 200}"/interpolate(scope) == "Test 200")

    # Using interpolate as a function.
    assert (interpolate("Test %{a}", scope) == "Test 321")
    assert (interpolate("Test %{a * 2}", scope) == "Test 642")
    assert (interpolate("Test %{100 if a == 123 else 200}", scope) == "Test 200")

    # Properly escaping sub strings.
    assert ('Test %{"asd"}'/interpolate == "Test asd")
    assert ("Test %{'asd'}"/interpolate == "Test asd")

    # Properly escaping sub braces.
    assert ("Test %{{'a': 123}['a']}"/interpolate == "Test 123")

    # Properly escaping.
    assert ("Test %%{a}"/interpolate == "Test %{a}")
    assert ("Test %%%{a}" / interpolate == "Test %%{a}")

    # Properly support argument placement
    assert ("Test %{a}"/interpolate(locals={"a": 123}) == "Test 123")
    assert ("Test %{a}"/interpolate({}, {"a": 123}) == "Test 123")

    # Multiple interpolation.
    assert("Test %{a} and %{a}"/interpolate == "Test 123 and 123")

    # Compiled tests.
    compiled = interpolate.compile("Test %{a}")
    assert (compiled.interpolate() == "Test 123")
    assert (compiled.interpolate({"a": 321}) == "Test 321")
    assert (compiled.interpolate(locals={"a": 321}) == "Test 321")

    print("Passed all tests.")