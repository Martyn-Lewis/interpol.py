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

class Interpolator(object):
    searcher = re.compile(r'(?<![%])%{')

    def __init__(self, _locals=None, _globals=None):
        self.locals = _locals
        self.globals = _globals

    def __call__(self, *args, **kwargs):
        if not len(args) and not len(kwargs):
            raise TypeError("Interpolator.__call__ takes at least 1 positional argument or 1 keyword argument, but 0 were given")

        _locals = self.locals
        _globals = self.globals
        _target = None

        # Derive scope from keyword arguments if provided.
        if 'locals' in kwargs:
            _locals = kwargs['locals']
        if 'globals' in kwargs:
            _globals = kwargs['globals']

        # Derive scope from arguments if provided.
        args = list(args)
        if len(args) and type(args[0]) is str: # (target, ...)
            _target = args[0]
            del args[0]

        if len(args): # (target, locals, ...)
            _locals = args[0]
            del args[0]

        if len(args): # (target, locals, globals)
            _globals = args[0]

        if supports_stack_inspection:
            if _locals is None:
                # Automatically try to obtain locals.
                # TODO: Move else where.
                frame = inspect.currentframe()
                parent = frame.f_back
                _locals = parent.f_locals

        if _locals is None:
            _locals = {}

        if _globals is None:
            _globals = globals()

        if _target is None:
            # Defer an interpolator for later use.
            return Interpolator(_locals, _globals)
        else:
            return Interpolator(_locals, _globals).__interpolate__(_target)

    def __rtruediv__(self, other):
        if not type(other) is str:
            raise TypeError("Attempted to infer interpolation with a non-string type, has your precedence been muddled? Check any x/interpolate")

        if self is interpolate:
            _locals = {}
            if supports_stack_inspection:
                # Automatically try to obtain locals.
                # TODO: Move somewhere else.
                frame = inspect.currentframe()
                parent = frame.f_back
                _locals = parent.f_locals

            return Interpolator(_locals).__interpolate__(other)
        else:
            return self.__interpolate__(other)

    def __interpolate__(self, string):
        _locals = self.locals or {}
        _globals = self.globals or globals()
        _components = []
        _search = Interpolator.searcher
        _offset = 0

        # This needs to be broken up for better parsing at some point.
        # Currently it's just testing "does this work?" and "how practical is this?"
        while True:
            match = _search.search(string, _offset)
            if not match:
                break

            # Make sure we capture the text in between.
            _components.append(string[_offset:match.start()].replace('%%{', '%{'))

            # We need to safely guarantee the behaviour of strings and dictionaries inside our expression.
            # Consider:
            #   %{"Hello there }"}
            #       - should properly end at the final }, not the } inside the string.
            #   %{{"a": 123}["a"]}
            #       - should properly end at the final }, not the dictionary's }.
            #   %{"sub interpolation %{\\\"just to confuse the hell out of you\\\"}"/interpolate}
            #       - should properly induce headaches.
            seek_from = match.end()
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
                        offset += 1
                        continue
                elif string[offset] in ['"', "'"]:
                    in_string = string[offset]
                    seek += 1
                    continue

                if string[offset] == '}':
                    seek += 1
                    if brace_counter > 0:
                        brace_counter -= 1
                        continue
                    else:
                        # We've finally escaped.
                        break

                if string[offset] == '{':
                    brace_counter += 1

                seek += 1
                continue
            evaluation = string[seek_from: seek_from + seek - 1]
            _components.append(eval(evaluation, _globals, _locals))
            _offset = seek_from + seek

        _components.append(string[_offset:].replace('%%{', '%{'))
        return "".join(str(x) for x in _components)

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
    assert ("Test %{{'a': 123}[a]}" == "Test 123")

    # Properly escaping.
    assert ("Test %%{a}" == "Test %{a}")

    # Properly support argument placement
    assert ("Test %{a}"/interpolate(locals={"a": 123}) == "Test 123")
    assert ("Test %{a}" / interpolate({}, {"a": 123}) == "Test 123")
