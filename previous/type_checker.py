from __future__ import annotations
from ast_nodes import (
    Program, Block, FunctionDecl, Stmt, Expr, IntLiteral, BoolLiteral, TypeName,
    VarDecl, Assignment, CallStmt, IfStmt, WhileStmt, ReturnStmt, PrintStmt,
    IdentifierExpr, UnaryExpr, BinaryExpr, CallExpr, BinaryOperator, UnaryOperator, StringLiteral
)

from semantic_errors import SemanticDiagnostic, SemanticError, SemanticErrorKind

UNKNOWN_TYPE = object()

class TypeChecker:
    """Determine tipos de expressões e valide seus contextos."""
    
    # 1. Use os símbolos anexados pela resolução de nomes.
    # 2. Determine cada expressão de baixo para cima.
    # 3. Valide operadores, chamadas, comandos e declarações.
    # 4. Anote expressões válidas e acumule os diagnósticos da passagem.

    def __init__(self, program: Program):
        self.program = program
        self.diagnostics: list[SemanticDiagnostic] = []

    def check(self):
        for function in self.program.functions:
            for param in function.parameters:
                if param.type == TypeName.VOID:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.VOID_PARAMETER,
                        f"Parâmetro '{param.name}' não pode ser void.",
                        param.span
                    ))
            
            self._check_block(function.body, function)

        if self.diagnostics:
            raise SemanticError(self.diagnostics)

    def _check_block(self, block: Block, function: FunctionDecl):
        for stmt in block.statements:
            self._check_stmt(stmt, function)
        
    def _check_stmt(self, stmt: Stmt, function: FunctionDecl):
        if isinstance(stmt, Block):
            self._check_block(stmt, function)
            return
            
        if isinstance(stmt, VarDecl):
            if stmt.type == TypeName.VOID:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.VOID_VARIABLE,
                    f"Variável '{stmt.name}' não pode ser void.",
                    stmt.span
                ))
                
            if getattr(stmt, 'initializer', None):
                init_type = self._check_expr(stmt.initializer)
                if init_type is not UNKNOWN_TYPE and stmt.type != TypeName.VOID and init_type != stmt.type:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.INITIALIZER_TYPE_MISMATCH,
                        "O tipo do inicializador não corresponde ao tipo da variável.",
                        stmt.initializer.span
                    ))
            return

        if isinstance(stmt, CallStmt):
            self._check_expr(stmt.call, allow_void=True)
            return

        if isinstance(stmt, Assignment):
            target_type = self._check_expr(stmt.target)
            value_type = self._check_expr(stmt.value)
            
            if target_type is not UNKNOWN_TYPE and value_type is not UNKNOWN_TYPE:
                if target_type != value_type:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.ASSIGNMENT_TYPE_MISMATCH,
                        "O tipo do valor não corresponde ao tipo da variável.",
                        stmt.value.span
                    ))
            return
                    
        if isinstance(stmt, IfStmt):
            condition_type = self._check_expr(stmt.condition, False)
            if condition_type != TypeName.BOOL:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.CONDITION_TYPE_MISMATCH,
                    "Condição deve ser um booleano",
                    span=stmt.condition.span
                ))
            self._check_block(stmt.then_block, function)
            if getattr(stmt, 'else_block', None):
                self._check_block(stmt.else_block, function)
            return
            
        if isinstance(stmt, WhileStmt):
            condition_type = self._check_expr(stmt.condition, False)
            if condition_type != TypeName.BOOL:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.CONDITION_TYPE_MISMATCH,
                    "Condição deve ser um booleano",
                    span=stmt.condition.span
                ))
            self._check_block(stmt.body, function)
            return
        

        if isinstance(stmt, ReturnStmt):
            if stmt.value is None:
                if function.return_type != TypeName.VOID:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.RETURN_MISMATCH,
                        "A função exige uma expressão de retorno.",
                        stmt.span
                    ))
                return

            return_type = self._check_expr(stmt.value)
            if return_type is not UNKNOWN_TYPE and return_type != function.return_type:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.RETURN_MISMATCH,
                    "O tipo de retorno não corresponde ao tipo da função.",
                    stmt.value.span
                ))
            return

        if isinstance(stmt, PrintStmt):
            for item in stmt.items:
                if isinstance(item, Expr):
                    self._check_expr(item)
            return

    def _check_expr(self, expr: Expr, allow_void: bool = False) -> TypeName | object:
        determined_type = self._check_type(expr, allow_void)
        if determined_type is not UNKNOWN_TYPE:
            expr.metadata["type"] = determined_type

        return determined_type

    def _check_type(self, expr: Expr, allow_void: bool) -> TypeName | object:
        if isinstance(expr, BoolLiteral):
            return TypeName.BOOL
        
        if isinstance(expr, IdentifierExpr):
            symbol = expr.metadata.get("symbol")
            if symbol:
                return symbol.type
            return UNKNOWN_TYPE

        if isinstance(expr, IntLiteral):
            if expr.value > 9223372036854775807:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.INTEGER_LITERAL_OUT_OF_RANGE,
                    "Literal inteiro além do limite (2^63 - 1)",
                    span=expr.span
                ))
            return TypeName.INT

        if isinstance(expr, BinaryExpr):
            left_type = self._check_expr(expr.left)
            right_type = self._check_expr(expr.right)
            
            if left_type is UNKNOWN_TYPE or right_type is UNKNOWN_TYPE:
                return UNKNOWN_TYPE
            
            operator = expr.operator
            if operator in {BinaryOperator.ADD, BinaryOperator.SUBTRACT, BinaryOperator.MULTIPLY, BinaryOperator.DIVIDE, BinaryOperator.REMAINDER}:
                if left_type != TypeName.INT or right_type != TypeName.INT:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.INVALID_BINARY_OPERANDS,
                        "Operadores aritméticos exigem operandos do tipo 'int'.",
                        expr.span
                    ))
                    return UNKNOWN_TYPE
                return TypeName.INT
            
            if operator in {BinaryOperator.LESS, BinaryOperator.LESS_EQUAL, BinaryOperator.GREATER, BinaryOperator.GREATER_EQUAL}:
                if left_type != TypeName.INT or right_type != TypeName.INT:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.INVALID_BINARY_OPERANDS,
                        "Operadores de comparação relacional exigem operandos do tipo 'int'.",
                        expr.span
                    ))
                    return UNKNOWN_TYPE
                return TypeName.BOOL
            
            if operator in {BinaryOperator.EQUAL, BinaryOperator.NOT_EQUAL}:
                if left_type != right_type or left_type not in {TypeName.INT, TypeName.BOOL}:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.INVALID_BINARY_OPERANDS,
                        "Operadores de igualdade exigem dois operandos do mesmo tipo não-nulo.",
                        expr.span
                    ))
                    return UNKNOWN_TYPE
                return TypeName.BOOL
            
            if operator in {BinaryOperator.LOGICAL_AND, BinaryOperator.LOGICAL_OR}:
                if left_type != TypeName.BOOL or right_type != TypeName.BOOL:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.INVALID_BINARY_OPERANDS,
                        "Operadores lógicos binários exigem operandos do tipo 'bool'.",
                        expr.span
                    ))
                    return UNKNOWN_TYPE
                return TypeName.BOOL

        if isinstance(expr, UnaryExpr):
            operand_type = self._check_expr(expr.operand)
            if operand_type == UNKNOWN_TYPE:
                return UNKNOWN_TYPE
            
            if expr.operator == UnaryOperator.NEGATE:
                if operand_type != TypeName.INT:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.INVALID_UNARY_OPERAND,
                        "O operador de inversão de sinal '-' requer uma expressão inteira.",
                        expr.span
                    ))
                    return UNKNOWN_TYPE
                return TypeName.INT
            
            if expr.operator == UnaryOperator.NOT:
                if operand_type != TypeName.BOOL:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.INVALID_UNARY_OPERAND,
                        "O operador lógico de negação '!' requer uma expressão booleana.",
                        expr.span
                    ))
                    return UNKNOWN_TYPE
                return TypeName.BOOL

        if isinstance(expr, CallExpr):
            symbol = expr.metadata.get("symbol")
            
            if not symbol:
                for argument in expr.arguments:
                    self._check_expr(argument)
                return UNKNOWN_TYPE
            
            if len(expr.arguments) != len(symbol.parameter_types):
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.ARITY_MISMATCH,
                    f"Quantidade de argumentos inválida para '{expr.name}'. Esperava {len(symbol.parameter_types)}, mas recebeu {len(expr.arguments)}.",
                    expr.span
                ))

            argument_types = [self._check_expr(argument) for argument in expr.arguments]
            for argument, argument_type, parameter_type in zip(
                expr.arguments, argument_types, symbol.parameter_types
            ):
                if argument_type is not UNKNOWN_TYPE and argument_type != parameter_type:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.ARGUMENT_TYPE_MISMATCH,
                        "O tipo do argumento não corresponde ao tipo do parâmetro.",
                        argument.span
                    ))

            return_type = symbol.type
            if return_type == TypeName.VOID and not allow_void:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.VOID_VALUE_USED,
                    f"Chamada de função '{expr.name}' do tipo void",
                    expr.span
                ))
                return UNKNOWN_TYPE

            return return_type
    
        return UNKNOWN_TYPE

def check_types(program: Program) -> None:
    TypeChecker(program).check()