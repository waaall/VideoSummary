"""条件表达式安全评估器"""

from __future__ import annotations

import ast
import operator
from typing import Any, Dict

# 允许的比较操作符
_ALLOWED_COMPARATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

# 允许的二元操作符
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
}

# 允许的一元操作符
_ALLOWED_UNARYOPS = {
    ast.Not: operator.not_,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class ConditionEvaluationError(Exception):
    """条件表达式评估错误"""

    pass


class ConditionEvaluator:
    """
    安全的条件表达式评估器

    支持：
    - 变量引用（从命名空间获取）
    - 比较操作（==, !=, <, <=, >, >=, in, not in, is, is not）
    - 布尔操作（and, or, not）
    - 算术操作（+, -, *, /, %）
    - 字面量（数字、字符串、布尔值、None、列表、元组）

    禁止：
    - 函数调用
    - 属性访问（除 True/False/None）
    - import / exec / eval
    - 赋值操作
    """

    def __init__(self, namespace: Dict[str, Any]):
        """
        初始化评估器

        Args:
            namespace: 可用变量的命名空间
        """
        self.namespace = namespace

    def evaluate(self, expression: str) -> bool:
        """
        安全评估条件表达式

        Args:
            expression: 条件表达式字符串

        Returns:
            评估结果（布尔值）

        Raises:
            ConditionEvaluationError: 表达式不合法或评估失败
        """
        if not expression or not expression.strip():
            return True

        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            raise ConditionEvaluationError(f"语法错误: {e}")

        try:
            result = self._eval_node(tree.body)
            return bool(result)
        except ConditionEvaluationError:
            raise
        except Exception as e:
            raise ConditionEvaluationError(f"评估失败: {e}")

    def _eval_node(self, node: ast.AST) -> Any:
        """递归评估 AST 节点"""
        # 字面量
        if isinstance(node, ast.Constant):
            return node.value

        # 变量引用
        if isinstance(node, ast.Name):
            if node.id in ("True", "False", "None"):
                return {"True": True, "False": False, "None": None}[node.id]
            if node.id not in self.namespace:
                raise ConditionEvaluationError(f"未知变量: {node.id}")
            return self.namespace[node.id]

        # 比较操作
        if isinstance(node, ast.Compare):
            return self._eval_compare(node)

        # 布尔操作（and/or）
        if isinstance(node, ast.BoolOp):
            return self._eval_boolop(node)

        # 一元操作（not, -）
        if isinstance(node, ast.UnaryOp):
            return self._eval_unaryop(node)

        # 二元操作（+, -, *, /, %）
        if isinstance(node, ast.BinOp):
            return self._eval_binop(node)

        # 列表
        if isinstance(node, ast.List):
            return [self._eval_node(elt) for elt in node.elts]

        # 元组
        if isinstance(node, ast.Tuple):
            return tuple(self._eval_node(elt) for elt in node.elts)

        # 集合
        if isinstance(node, ast.Set):
            return {self._eval_node(elt) for elt in node.elts}

        # 字典
        if isinstance(node, ast.Dict):
            return {
                self._eval_node(k): self._eval_node(v)
                for k, v in zip(node.keys, node.values)
            }

        # IfExp (三元表达式)
        if isinstance(node, ast.IfExp):
            if self._eval_node(node.test):
                return self._eval_node(node.body)
            return self._eval_node(node.orelse)

        # 禁止的操作
        raise ConditionEvaluationError(
            f"不支持的操作: {type(node).__name__}"
        )

    def _eval_compare(self, node: ast.Compare) -> bool:
        """评估比较表达式"""
        left = self._eval_node(node.left)

        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in _ALLOWED_COMPARATORS:
                raise ConditionEvaluationError(f"不支持的比较操作: {op_type.__name__}")

            right = self._eval_node(comparator)
            op_func = _ALLOWED_COMPARATORS[op_type]

            if not op_func(left, right):
                return False
            left = right

        return True

    def _eval_boolop(self, node: ast.BoolOp) -> bool:
        """评估布尔操作（and/or）"""
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not self._eval_node(value):
                    return False
            return True
        elif isinstance(node.op, ast.Or):
            for value in node.values:
                if self._eval_node(value):
                    return True
            return False
        else:
            raise ConditionEvaluationError(f"不支持的布尔操作: {type(node.op).__name__}")

    def _eval_unaryop(self, node: ast.UnaryOp) -> Any:
        """评估一元操作"""
        op_type = type(node.op)
        if op_type not in _ALLOWED_UNARYOPS:
            raise ConditionEvaluationError(f"不支持的一元操作: {op_type.__name__}")

        operand = self._eval_node(node.operand)
        return _ALLOWED_UNARYOPS[op_type](operand)

    def _eval_binop(self, node: ast.BinOp) -> Any:
        """评估二元操作"""
        op_type = type(node.op)
        if op_type not in _ALLOWED_BINOPS:
            raise ConditionEvaluationError(f"不支持的二元操作: {op_type.__name__}")

        left = self._eval_node(node.left)
        right = self._eval_node(node.right)
        return _ALLOWED_BINOPS[op_type](left, right)


def evaluate_condition(expression: str, namespace: Dict[str, Any]) -> bool:
    """
    便捷函数：安全评估条件表达式

    Args:
        expression: 条件表达式字符串
        namespace: 可用变量的命名空间

    Returns:
        评估结果（布尔值）
    """
    evaluator = ConditionEvaluator(namespace)
    return evaluator.evaluate(expression)
