from __future__ import annotations
from semantic_errors import SemanticDiagnostic, SemanticErrorKind, SemanticError
from symbols import FunctionSymbol, Scope, Symbol, SymbolKind, TypeName
from ast_nodes import (
    Program, 
    Block, 
    Stmt, 
    VarDecl, 
    CallExpr, 
    IdentifierExpr, 
    Expr, 
    Assignment, 
    CallStmt,
    IfStmt,
    WhileStmt,
    ReturnStmt,
    PrintStmt,
    CallExpr,
    IdentifierExpr,
    BinaryExpr,
    UnaryExpr,
)


class NameResolver:
    # 1. Colete todas as assinaturas de função.
    # 2. Valide a existência e a assinatura de main.
    # 3. Percorra os corpos em ordem, criando um escopo para cada bloco.
    # 4. Anote declarações, usos e blocos na AST.
    # 5. Acumule os diagnósticos desta passagem antes de lançar SemanticError.
    
    def __init__(self, program: Program):
        self.program = program
        self.diagnostics: list[SemanticDiagnostic] = []
        self.functions_table: dict[str, FunctionSymbol] = {}

    def resolve(self):
        self._collect_functions()
        self._resolve_blocks()

        if self.diagnostics:
            raise SemanticError(self.diagnostics)
    
    def _collect_functions(self):
        for function in self.program.functions:
            param_types = tuple(parameter.type for parameter in function.parameters)
            func_symbol = FunctionSymbol(
                name= function.name, 
                kind= SymbolKind.FUNCTION,
                type= function.return_type, 
                declaration= function,
                parameter_types= param_types
            )

            function.metadata["symbol"] = func_symbol

            # Valida a existência de funções duplicadas
            if function.name in self.functions_table:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.DUPLICATE_FUNCTION,
                    f"Função '{function.name}' já declarada.",
                    function.span
                ))
            else:
                self.functions_table[function.name] = func_symbol


        # Valida a existência e assinatura da função main
        main_symbol = self.functions_table.get("main")
        if not main_symbol:
            self.diagnostics.append(SemanticDiagnostic(
                SemanticErrorKind.INVALID_MAIN,
                f"Função 'main' não declarada",
                self.program.span
            ))
        elif main_symbol.type != TypeName.INT or len(main_symbol.parameter_types) != 0:
            self.diagnostics.append(SemanticDiagnostic(
                SemanticErrorKind.INVALID_MAIN,
                f"A função main deve possuir a assinatura exata: 'int main()'.",
                self.program.span
            ))
        
    def _resolve_blocks(self):
        # for function_name, value in self.functions_table.items():
        for function in self.program.functions:
            function_scope = Scope(parent = None)

            # Valida os parâmetros duplicados
            for param in function.parameters:
                if param.name in function_scope.symbols:
                    self.diagnostics.append(SemanticDiagnostic(
                        SemanticErrorKind.DUPLICATE_DECLARATION,
                        f"Parâmetro '{param.name}' já declarado.",
                        param.span
                    ))
                else:
                    param_symbol = Symbol(
                        name= param.name,
                        kind= SymbolKind.PARAMETER,
                        type= param.type,
                        declaration= param
                    )
                    function_scope.symbols[param.name] = param_symbol
                    param.metadata["symbol"] = param_symbol

            function.body.metadata["scope"] = function_scope

            # Resolve os blocos da função
            for stmt in function.body.statements:
                self._resolve_stmt(stmt, function_scope)

    def _resolve_block(self, block: Block, parent_scope: Scope):
        new_scope = Scope(parent= parent_scope)
        block.metadata["scope"] = new_scope

        for stmt in block.statements:
            self._resolve_stmt(stmt, new_scope)

    def _resolve_stmt(self, stmt: Stmt, scope: Scope):
        # Valida se é um bloco e entra recursivo
        if isinstance(stmt, Block):
            self._resolve_block(stmt, scope)
            return

        # Valida se ja foi declarada
        if isinstance(stmt, VarDecl):
            if stmt.name in scope.symbols:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.DUPLICATE_DECLARATION,
                    f"Variavel '{stmt.name}' já foi declarada no mesmo escopo.",
                    stmt.span
                ))
            else:
                self._set_symbol(stmt, scope, SymbolKind.VARIABLE)

            if getattr(stmt, 'initializer', None):
                self._resolve_expr(stmt.initializer, scope)
            return

        if isinstance(stmt, CallStmt):
            self._resolve_expr(stmt.call, scope)
            return

        if isinstance(stmt, Assignment):
            self._resolve_expr(stmt.target, scope)
            self._resolve_expr(stmt.value, scope)

            return

        if isinstance(stmt, IfStmt):
            self._resolve_block(stmt.then_block, scope)
            self._resolve_expr(stmt.condition, scope)
            if getattr(stmt, 'else_block', None):
                self._resolve_block(stmt.else_block, scope)
            return

        if isinstance(stmt, WhileStmt):
            self._resolve_block(stmt.body, scope)
            self._resolve_expr(stmt.condition, scope)
            return

        if isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                self._resolve_expr(stmt.value, scope)
            return

        if isinstance(stmt, PrintStmt):
            for item in stmt.items:
                self._resolve_expr(item, scope)
            return

        print("ver aqui", stmt)

    def _resolve_expr(self, expr: Expr, scope: Scope):
        if isinstance(expr, BinaryExpr):
            self._resolve_expr(expr.left, scope)
            self._resolve_expr(expr.right, scope)
            return

        if isinstance(expr, UnaryExpr):
            self._resolve_expr(expr.operand, scope)
            return

        if isinstance(expr, CallExpr):
            function = self.functions_table.get(expr.name, None)
            if function:
                expr.metadata["symbol"] = function
            else:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.UNDECLARED_FUNCTION,
                    f"Funcao '{expr.name}' nao foi declarada",
                    expr.span
                ))
                                        
            for arg in expr.arguments:
                self._resolve_expr(arg, scope)

            return

        if isinstance(expr, IdentifierExpr):
            found_expr = self._find_expr(expr, scope)

            if not found_expr:
                self.diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.UNDECLARED_VARIABLE,
                    f"Variavel '{expr.name}' nao foi declarada",
                    expr.span
                ))

            return

    def _set_symbol(self, stmt: Stmt, scope: Scope, kind: SymbolKind):
        var_symbol = Symbol(
            name=stmt.name,
            kind=kind,
            type=stmt.type,
            declaration=stmt
        )
        scope.symbols[stmt.name] = var_symbol
        stmt.metadata["symbol"] = var_symbol

    def _find_expr(self, expr: Expr, scope: Scope):
        symbol_in_scope = scope.symbols.get(expr.name, None)
        while scope is not None:
            if expr.name not in scope.symbols:
                scope = scope.parent
            else:
                symbol_in_scope = scope.symbols.get(expr.name)
                expr.metadata["symbol"] = symbol_in_scope
                break
        
        return symbol_in_scope

def resolve_names(program: Program) -> None:
    NameResolver(program).resolve()