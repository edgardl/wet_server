"""Bounded interpreter for XC's explicit procedural extension.

Expressions use Python's expression *syntax*, never its code execution engine.
Capabilities are trusted host objects: this is an execution boundary, not a
security sandbox for hostile capabilities. Records describe adapter methods.
"""
from __future__ import annotations

import ast
import builtins
import inspect
import operator
import re
from types import SimpleNamespace


class XCProcedureError(ValueError):
    pass


class XCBudgetError(RuntimeError):
    pass


class _Scope(dict):
    def __init__(self, parent=None, **values):
        super().__init__(values)
        self.parent = parent

    def lookup(self, name):
        if name in self:
            return self[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        raise NameError(name)


class _Flow(BaseException):
    def __init__(self, kind, value=None):
        self.kind, self.value = kind, value


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow, ast.BitOr: operator.or_,
        ast.BitAnd: operator.and_, ast.BitXor: operator.xor,
        ast.LShift: operator.lshift, ast.RShift: operator.rshift}
_CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
        ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
        ast.Is: operator.is_, ast.IsNot: operator.is_not,
        ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos,
          ast.Not: operator.not_, ast.Invert: operator.invert}
_BUILTINS = ('abs all any bool dict enumerate filter float frozenset int len list '
             'map max min next iter print range reversed round set sorted str sum tuple type '
             'zip isinstance getattr hasattr setattr ValueError TypeError '
             'KeyError IndexError RuntimeError StopIteration').split()


class _Namespace:
    def __init__(self, scope):
        self._scope = scope

    def __getattr__(self, name):
        try:
            return self._scope[name]
        except KeyError:
            raise AttributeError(name) from None


class XCProcedures:
    def __init__(self, text, capabilities=None, *, max_steps=2_000_000, max_depth=128):
        self.max_steps, self.max_depth = max_steps, max_depth
        self._steps = self._depth = 0
        self.namespaces, self.records = {}, {}
        self.globals = _Scope()
        self.globals.update({n: getattr(builtins, n) for n in _BUILTINS})
        self.globals.update(true=True, false=False, null=None)
        self.globals.update(capabilities or {})
        lines = [(i, line.strip()) for i, line in enumerate(text.splitlines(), 1)
                 if line.strip() and not line.strip().startswith('//')]
        if not lines or not re.fullmatch(r'procedures \w+ version 1 \{', lines[0][1]):
            raise XCProcedureError('expected procedures NAME version 1 {')
        self._lines, self._pos = lines, 1
        body = self._parse_block()
        if self._pos != len(lines):
            raise XCProcedureError('trailing source after procedures block')
        # Make all namespaces available before initializing their definitions.
        for kind, payload, _ in body:
            if kind != 'namespace':
                raise XCProcedureError('only namespaces belong at procedure root')
            scope = _Scope(self.globals)
            self.namespaces[payload] = _Namespace(scope)
            self.globals[payload] = self.namespaces[payload]
        for _, name, statements in body:
            self._run(statements, self.namespaces[name]._scope)

    def _tick(self):
        self._steps += 1
        if self._steps > self.max_steps:
            raise XCBudgetError('XC instruction budget exceeded')

    def _expr(self, text):
        try:
            node = ast.parse(text.strip(), mode='eval').body
        except SyntaxError as exc:
            raise XCProcedureError(f'invalid XC expression: {text}') from exc
        allowed = (ast.Constant, ast.Name, ast.List, ast.Tuple, ast.Set, ast.Dict,
                   ast.Attribute, ast.Subscript, ast.Slice, ast.BinOp, ast.UnaryOp,
                   ast.BoolOp, ast.Compare, ast.IfExp, ast.Call, ast.keyword,
                   ast.Starred, ast.Lambda, ast.arguments, ast.arg, ast.ListComp,
                   ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
                   ast.JoinedStr, ast.FormattedValue, ast.Load, ast.Store,
                   ast.operator, ast.unaryop, ast.boolop, ast.cmpop)
        for child in ast.walk(node):
            if not isinstance(child, allowed) or (isinstance(child, ast.comprehension) and child.is_async):
                raise XCProcedureError(f'unsupported expression: {type(child).__name__}')
            if isinstance(child, ast.Attribute) and child.attr.startswith('__'):
                raise XCProcedureError('dunder attribute access is unsupported')
        return node

    def _parse_block(self):
        result = []
        while self._pos < len(self._lines):
            number, line = self._lines[self._pos]
            self._pos += 1
            if line == '}':
                return result
            if line.endswith('{'):
                header = line[:-1].strip()
                match = re.fullmatch(r'(namespace|record) (\w+)', header)
                if match:
                    kind, payload = match.groups()
                elif header.startswith(('fn ', 'property ')):
                    kind, declaration = header.split(' ', 1)
                    match = re.fullmatch(r'(\w+)\((.*)\)', declaration)
                    if not match:
                        raise XCProcedureError(f'bad function at line {number}')
                    name, params = match.groups()
                    args = self._expr('lambda ' + params + ': None').args
                    payload = (name, args)
                elif header.startswith('if '):
                    kind, payload = 'if', self._expr(header[3:])
                elif header.startswith('while '):
                    kind, payload = 'while', self._expr(header[6:])
                elif header.startswith('for '):
                    target, sep, expression = header[4:].partition(' in ')
                    if not sep:
                        raise XCProcedureError(f'bad for at line {number}')
                    kind, payload = 'for', (self._expr('(' + target + ')'), self._expr(expression))
                else:
                    raise XCProcedureError(f'unsupported block at line {number}: {header}')
                block = self._parse_block()
                if kind == 'if':
                    alternate = []
                    if self._pos < len(self._lines) and self._lines[self._pos][1] == 'else {':
                        self._pos += 1
                        alternate = self._parse_block()
                    block = (block, alternate)
                result.append((kind, payload, block))
                continue
            if not line.endswith(';'):
                raise XCProcedureError(f'expected statement terminator at line {number}')
            line = line[:-1].strip()
            if line.startswith('let '):
                target, sep, expression = line[4:].partition(' <- ')
                if not sep:
                    raise XCProcedureError(f'bad assignment at line {number}')
                result.append(('let', (self._expr('(' + target + ')'), self._expr(expression)), None))
            elif line in ('return', 'break', 'continue'):
                result.append((line, None, None))
            elif line.startswith(('return ', 'raise ', 'remove ')):
                kind, expression = line.split(' ', 1)
                result.append((kind, self._expr(expression), None))
            else:
                result.append(('expr', self._expr(line), None))
        raise XCProcedureError('unclosed XC block')

    def _function(self, args, body, closure, expression=False):
        params = []
        positional = args.posonlyargs + args.args
        defaults = [inspect.Parameter.empty] * (len(positional) - len(args.defaults))
        defaults += [self._eval(n, closure) for n in args.defaults]
        for i, (arg, default) in enumerate(zip(positional, defaults)):
            kind = inspect.Parameter.POSITIONAL_ONLY if i < len(args.posonlyargs) else inspect.Parameter.POSITIONAL_OR_KEYWORD
            params.append(inspect.Parameter(arg.arg, kind, default=default))
        if args.vararg:
            params.append(inspect.Parameter(args.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
        for arg, default in zip(args.kwonlyargs, args.kw_defaults):
            params.append(inspect.Parameter(arg.arg, inspect.Parameter.KEYWORD_ONLY,
                          default=inspect.Parameter.empty if default is None else self._eval(default, closure)))
        if args.kwarg:
            params.append(inspect.Parameter(args.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
        signature = inspect.Signature(params)

        def call(*values, **keywords):
            if self._depth == 0:
                self._steps = 0
            if self._depth >= self.max_depth:
                raise XCBudgetError('XC call depth exceeded')
            bound = signature.bind(*values, **keywords)
            bound.apply_defaults()
            local = _Scope(closure)
            local.update(bound.arguments)
            self._depth += 1
            try:
                if expression:
                    return self._eval(body, local)
                self._run(body, local)
            except _Flow as flow:
                if flow.kind != 'return':
                    raise XCProcedureError(f'{flow.kind} outside loop') from None
                return flow.value
            finally:
                self._depth -= 1
        call.__signature__ = signature
        return call

    def _assign(self, target, value, scope, remove=False):
        self._tick()
        if isinstance(target, ast.Name):
            if remove:
                del scope[target.id]
            else:
                scope[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)) and not remove:
            values = list(value)
            stars = [i for i, item in enumerate(target.elts) if isinstance(item, ast.Starred)]
            if not stars:
                if len(values) != len(target.elts):
                    raise ValueError('unpack length mismatch')
                for item, val in zip(target.elts, values):
                    self._assign(item, val, scope)
            else:
                if len(stars) != 1 or len(values) < len(target.elts) - 1:
                    raise ValueError('unpack length mismatch')
                index = stars[0]
                end = len(values) - (len(target.elts) - index - 1)
                unpacked = values[:index] + [values[index:end]] + values[end:]
                for item, val in zip(target.elts, unpacked):
                    self._assign(item.value if isinstance(item, ast.Starred) else item, val, scope)
        elif isinstance(target, ast.Attribute):
            obj = self._eval(target.value, scope)
            if remove:
                delattr(obj, target.attr)
            else:
                setattr(obj, target.attr, value)
        elif isinstance(target, ast.Subscript):
            obj, index = self._eval(target.value, scope), self._eval(target.slice, scope)
            if remove:
                del obj[index]
            else:
                obj[index] = value
        else:
            raise XCProcedureError('unsupported assignment target')

    def _run(self, statements, scope):
        for kind, payload, body in statements:
            self._tick()
            if kind == 'let':
                self._assign(payload[0], self._eval(payload[1], scope), scope)
            elif kind == 'remove':
                self._assign(payload, None, scope, remove=True)
            elif kind == 'expr':
                self._eval(payload, scope)
            elif kind in ('return', 'break', 'continue'):
                raise _Flow(kind, self._eval(payload, scope) if payload is not None else None)
            elif kind == 'raise':
                raise self._eval(payload, scope)
            elif kind in ('fn', 'property'):
                scope[payload[0]] = self._function(payload[1], body, scope)
            elif kind == 'record':
                record = SimpleNamespace(methods={}, properties={})
                for method_kind, declaration, method_body in body:
                    if method_kind not in ('fn', 'property'):
                        raise XCProcedureError('records contain methods and properties only')
                    mapping = record.methods if method_kind == 'fn' else record.properties
                    mapping[declaration[0]] = self._function(declaration[1], method_body, scope)
                self.records[payload] = record
            elif kind == 'if':
                self._run(body[0] if self._eval(payload, scope) else body[1], scope)
            elif kind in ('while', 'for'):
                iterator = iter(self._eval(payload[1], scope)) if kind == 'for' else None
                while True:
                    self._tick()
                    if kind == 'for':
                        try:
                            value = next(iterator)
                        except StopIteration:
                            break
                        self._assign(payload[0], value, scope)
                    elif not self._eval(payload, scope):
                        break
                    try:
                        self._run(body, scope)
                    except _Flow as flow:
                        if flow.kind == 'break':
                            break
                        if flow.kind != 'continue':
                            raise
            else:
                raise XCProcedureError(f'unsupported statement {kind}')

    def _eval(self, node, scope):
        self._tick()
        ev = lambda n: self._eval(n, scope)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return scope.lookup(node.id)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = []
            for n in node.elts:
                values.extend(ev(n.value)) if isinstance(n, ast.Starred) else values.append(ev(n))
            return {ast.List: list, ast.Tuple: tuple, ast.Set: set}[type(node)](values)
        if isinstance(node, ast.Dict):
            result = {}
            for k, v in zip(node.keys, node.values):
                if k is None:
                    result.update(ev(v))
                else:
                    result[ev(k)] = ev(v)
            return result
        if isinstance(node, ast.Attribute):
            return getattr(ev(node.value), node.attr)
        if isinstance(node, ast.Subscript):
            return ev(node.value)[ev(node.slice)]
        if isinstance(node, ast.Slice):
            return slice(*(ev(n) if n is not None else None for n in (node.lower, node.upper, node.step)))
        if isinstance(node, ast.BinOp):
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp):
            return _UNARY[type(node.op)](ev(node.operand))
        if isinstance(node, ast.BoolOp):
            result = ev(node.values[0])
            for n in node.values[1:]:
                if (isinstance(node.op, ast.And) and not result) or (isinstance(node.op, ast.Or) and result):
                    return result
                result = ev(n)
            return result
        if isinstance(node, ast.Compare):
            left = ev(node.left)
            for op, right_node in zip(node.ops, node.comparators):
                right = ev(right_node)
                if not _CMP[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return ev(node.body if ev(node.test) else node.orelse)
        if isinstance(node, ast.Call):
            function = ev(node.func)
            args, keywords = [], {}
            for n in node.args:
                args.extend(ev(n.value)) if isinstance(n, ast.Starred) else args.append(ev(n))
            for kw in node.keywords:
                incoming = {kw.arg: ev(kw.value)} if kw.arg is not None else ev(kw.value)
                for key, val in incoming.items():
                    if key in keywords:
                        raise TypeError(f'multiple values for keyword {key}')
                    keywords[key] = val
            return function(*args, **keywords)
        if isinstance(node, ast.Lambda):
            return self._function(node.args, node.body, scope, expression=True)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            local = _Scope(scope)
            # Python captures the outer iterable when constructing a generator.
            first = iter(ev(node.generators[0].iter))
            def generate(index=0):
                gen = node.generators[index]
                iterable = first if index == 0 else self._eval(gen.iter, local)
                for val in iterable:
                    self._tick()
                    self._assign(gen.target, val, local)
                    if all(self._eval(cond, local) for cond in gen.ifs):
                        if index + 1 < len(node.generators):
                            yield from generate(index + 1)
                        elif isinstance(node, ast.DictComp):
                            yield self._eval(node.key, local), self._eval(node.value, local)
                        else:
                            yield self._eval(node.elt, local)
            iterator = generate()
            if isinstance(node, ast.GeneratorExp):
                return iterator
            return (dict if isinstance(node, ast.DictComp) else set if isinstance(node, ast.SetComp) else list)(iterator)
        if isinstance(node, ast.JoinedStr):
            return ''.join(ev(n) for n in node.values)
        if isinstance(node, ast.FormattedValue):
            val = ev(node.value)
            if node.conversion != -1:
                val = {115: str, 114: repr, 97: ascii}[node.conversion](val)
            return format(val, ev(node.format_spec) if node.format_spec else '')
        raise XCProcedureError(f'unsupported expression: {type(node).__name__}')
