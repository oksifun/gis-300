import ast
import operator


unaryOps = {
    ast.UAdd: lambda x: x,
    ast.USub: operator.neg,
}

binOps = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}


def math_eval(s, scope=None):
    if scope is None:
        scope = {}
    node = ast.parse(s, mode='eval')

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.UnaryOp):
            return unaryOps[type(node.op)](_eval(node.operand))
        elif isinstance(node, ast.BinOp):
            try:
                return binOps[type(node.op)](_eval(node.left), _eval(node.right))
            except ZeroDivisionError:
                return 0
        elif isinstance(node, ast.Name):
            return scope[node.id]
        else:
            raise Exception('Unsupported type {}'.format(node))

    return _eval(node.body)

