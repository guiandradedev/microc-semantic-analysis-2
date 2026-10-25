from __future__ import annotations

from collections.abc import Sequence

from Lexer import Token, TokenKind
from ast_nodes import (
    Block,
    Expr,
    FunctionDecl,
    Node,
    Parameter,
    PrintItem,
    Program,
    SourceSpan,
    Stmt,
    StringLiteral,
    TypeName,
    VarDecl,
    IfStmt,
    WhileStmt,
    ReturnStmt,
    BinaryExpr,
    BinaryOperator,
    PrintStmt,
    PrintItem,
    UnaryOperator,
    UnaryExpr,
    CallExpr,
    IdentifierExpr,
    IntLiteral,
    BoolLiteral,
    Assignment,
    CallStmt
)


TYPE_START = {TokenKind.KW_INT, TokenKind.KW_BOOL, TokenKind.KW_VOID}
EXPRESSION_START = {
    TokenKind.IDENTIFIER,
    TokenKind.INT_LITERAL,
    TokenKind.KW_FALSE,
    TokenKind.KW_TRUE,
    TokenKind.LEFT_PAREN,
    TokenKind.LOGICAL_NOT,
    TokenKind.MINUS,
}
STATEMENT_START = TYPE_START | {
    TokenKind.IDENTIFIER,
    TokenKind.KW_IF,
    TokenKind.KW_WHILE,
    TokenKind.KW_RETURN,
    TokenKind.KW_PRINT,
    TokenKind.LEFT_BRACE,
}


TYPE_BY_TOKEN = {
    TokenKind.KW_INT: TypeName.INT,
    TokenKind.KW_BOOL: TypeName.BOOL,
    TokenKind.KW_VOID: TypeName.VOID,
}


class ParserError(Exception):
    def __init__(self, token: Token, expected: set[TokenKind]):
        self.token = token
        self.expected = frozenset(expected)
        super().__init__()

    @property
    def line(self) -> int:
        return self.token.line

    @property
    def column(self) -> int:
        return self.token.column

    def __str__(self) -> str:
        names = ", ".join(kind.name for kind in sorted(
            self.expected,
            key=lambda kind: kind.value,
        ))
        return (
            f"erro sintático em {self.line}:{self.column}: esperado {{{names}}}, "
            f"encontrado {self.token.kind.name} ({self.token.lexeme!r})"
        )


class Parser:
    def __init__(self, tokens: Sequence[Token]):
        self.tokens = list(tokens)
        if not self.tokens:
            raise ValueError("a sequência de tokens deve terminar em EOF")
        if self.tokens[-1].kind is not TokenKind.EOF:
            raise ValueError("o último token deve ser EOF")
        if any(token.kind is TokenKind.EOF for token in self.tokens[:-1]):
            raise ValueError("EOF deve aparecer uma única vez, no final")
        self.current = 0

    def peek(self, offset: int = 0) -> Token:
        index = min(self.current + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def check(self, kind: TokenKind) -> bool:
        return self.peek().kind is kind

    def advance(self) -> Token:
        token = self.peek()
        if self.current < len(self.tokens) - 1:
            self.current += 1
        return token

    def match(self, *kinds: TokenKind) -> Token | None:
        if self.peek().kind in kinds:
            return self.advance()
        return None

    def expect(self, kinds: TokenKind | set[TokenKind]) -> Token:
        expected = kinds if isinstance(kinds, set) else {kinds}
        token = self.peek()
        if token.kind not in expected:
            raise ParserError(token, set(expected))
        return self.advance()

    @staticmethod
    def _token_span(token: Token) -> SourceSpan:
        return SourceSpan(
            token.line,
            token.column,
            token.line,
            token.column + len(token.lexeme),
        )

    @staticmethod
    def _start(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.start_line, value.span.start_column
        return value.line, value.column

    @staticmethod
    def _end(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.end_line, value.span.end_column
        return value.line, value.column + len(value.lexeme)

    @classmethod
    def _span(cls, first: Token | Node, last: Token | Node) -> SourceSpan:
        start_line, start_column = cls._start(first)
        end_line, end_column = cls._end(last)
        return SourceSpan(start_line, start_column, end_line, end_column)

    def parse(self) -> Program:
        return self.parse_program()

    def parse_program(self) -> Program:
        # program ::= function* EOF
        start = self.peek()
        functions: list[FunctionDecl] = []
        while self.peek().kind in TYPE_START:
            functions.append(self.parse_function())
        eof = self.expect(TokenKind.EOF)
        return Program(functions, span=self._span(start, eof))

    def parse_function(self) -> FunctionDecl:
        # function ::= type IDENTIFIER ... block
        start = self.peek()
        return_type = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)
        self.expect(TokenKind.LEFT_PAREN)
        parameters = (
            self.parse_parameter_list()
            if self.peek().kind in TYPE_START
            else []
        )
        self.expect(TokenKind.RIGHT_PAREN)
        body = self.parse_block()
        return FunctionDecl(
            return_type,
            name.lexeme,
            parameters,
            body,
            span=self._span(start, body),
        )

    def parse_type(self) -> TypeName:
        # type ::= KW_INT | KW_BOOL | KW_VOID
        token = self.expect(TYPE_START)
        return TYPE_BY_TOKEN[token.kind]

    def parse_parameter_list(self) -> list[Parameter]:
        # parameter_list ::= parameter (COMMA parameter)*
        parameters = [self.parse_parameter()]
        while self.match(TokenKind.COMMA):
            parameters.append(self.parse_parameter())
        return parameters

    def parse_parameter(self) -> Parameter:
        # parameter ::= type IDENTIFIER
        start = self.peek()
        type_param = self.parse_type()
        identifier = self.expect(TokenKind.IDENTIFIER)
        
        return Parameter(type_param, identifier.lexeme, span=self._span(start, identifier))

    def parse_block(self) -> Block:
        # block ::= LEFT_BRACE statement* RIGHT_BRACE
        start = self.expect(TokenKind.LEFT_BRACE)
        
        statements: list[Stmt] = []
        while not self.check(TokenKind.RIGHT_BRACE):
            statements.append(self.parse_statement())
        
        end = self.expect(TokenKind.RIGHT_BRACE)
        return Block(statements, span=self._span(start, end))

    def parse_statement(self) -> Stmt:
        """
        statement ::= declaration
            | id_or_call_statement
            | if_statement
            | while_statement
            | return_statement
            | print_statement
            | block
        """
        
        token = self.peek()
        
        # Decisao pelo token atual
        if token.kind in TYPE_START:
            return self.parse_declaration()
        elif token.kind == TokenKind.IDENTIFIER:
            return self.parse_id_or_call_statement()
        elif token.kind == TokenKind.KW_IF:
            return self.parse_if_statement()
        elif token.kind == TokenKind.KW_WHILE:
            return self.parse_while_statement()
        elif token.kind == TokenKind.KW_RETURN:
            return self.parse_return_statement()
        elif token.kind == TokenKind.KW_PRINT:
            return self.parse_print_statement()
        elif token.kind == TokenKind.LEFT_BRACE:
            return self.parse_block()
        else:
            raise ParserError(token, STATEMENT_START)
        

    def parse_id_or_call_statement(self) -> Stmt:
        start = self.expect(TokenKind.IDENTIFIER)
        
        if self.match(TokenKind.ASSIGN):
            value = self.parse_expression()
            end = self.expect(TokenKind.SEMICOLON)
            
            target = IdentifierExpr(start.lexeme, span=self._token_span(start))
            return Assignment(target, value, span=self._span(start, end))
            
        elif self.match(TokenKind.LEFT_PAREN):
            args = self.parse_arguments()
            right_paren = self.expect(TokenKind.RIGHT_PAREN)
            end = self.expect(TokenKind.SEMICOLON)
            
            call = CallExpr(start.lexeme, args, span=self._span(start, right_paren))
            return CallStmt(call, span=self._span(start, end))
        else:
            raise ParserError(self.peek(), {TokenKind.ASSIGN, TokenKind.LEFT_PAREN})

    def parse_declaration(self) -> Stmt:
        # declaration ::= type IDENTIFIER (ASSIGN expression)? SEMICOLON
        start = self.peek()
        declaration_type = self.parse_type()
        identifier = self.expect(TokenKind.IDENTIFIER)
        
        value = None
        if self.match(TokenKind.ASSIGN):
            value = self.parse_expression()
        
        end = self.expect(TokenKind.SEMICOLON)
        return VarDecl(declaration_type, identifier.lexeme, value, span=self._span(start, end))
    
    def parse_if_statement(self) -> Stmt:
        # if_statement ::= KW_IF LEFT_PAREN expression RIGHT_PAREN block (KW_ELSE block)?
        start = self.expect(TokenKind.KW_IF)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        then_block = self.parse_block()

        else_block = None
        if self.match(TokenKind.KW_ELSE):
            else_block = self.parse_block()

        end = then_block if else_block else then_block
        
        return IfStmt(condition,then_block,else_block,span=self._span(start, end))

    def parse_while_statement(self) -> Stmt:
        # while_statement ::= KW_WHILE LEFT_PAREN expression RIGHT_PAREN block
        start = self.expect(TokenKind.KW_WHILE)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        
        block = self.parse_block()
        return WhileStmt(condition, block, span=self._span(start, block))
    
    def parse_return_statement(self) -> Stmt:
        # return_statement ::= KW_RETURN expression? SEMICOLON
        start = self.expect(TokenKind.KW_RETURN)
        
        expression = None
        if not self.check(TokenKind.SEMICOLON):
            expression = self.parse_expression()
        
        end = self.expect(TokenKind.SEMICOLON)
        return ReturnStmt(expression, span=self._span(start, end))

    def parse_print_statement(self) -> Stmt:
        # print_statement ::= KW_PRINT LEFT_PAREN print_item (COMMA print_item)* RIGHT_PAREN SEMICOLON
        start = self.expect(TokenKind.KW_PRINT)
        self.expect(TokenKind.LEFT_PAREN)

        items = [self.parse_print_item()]
        while self.match(TokenKind.COMMA):
            items.append(self.parse_print_item())
        
        self.expect(TokenKind.RIGHT_PAREN)
        end = self.expect(TokenKind.SEMICOLON)
        return PrintStmt(
            items,
            span=self._span(start, end)
        )

    def parse_print_item(self) -> PrintItem:
        # print_item ::= expression | string_literals
        if self.check(TokenKind.STRING_LITERAL):
            return self.parse_string_literals()
        
        token = self.peek()
        if token.kind in EXPRESSION_START:
            return self.parse_expression()

        raise ParserError(token, STATEMENT_START | {TokenKind.STRING_LITERAL})


    def parse_string_literals(self) -> StringLiteral:
        # string_literals ::= STRING_LITERAL+
        start = self.expect(TokenKind.STRING_LITERAL)
        value = str(start.value)

        end = start
        while self.check(TokenKind.STRING_LITERAL):
            token = self.advance()
            value += str(token.value)
            end = token

        return StringLiteral(value, span=self._span(start, end))


    def parse_expression(self) -> Expr:
        # expression ::= logical_or
        return self.parse_logical_or()

    def parse_logical_or(self) -> Expr:
        # logical_or ::= logical_and (LOGICAL_OR logical_and)*
        left = self.parse_logical_and()

        while self.check(TokenKind.LOGICAL_OR):
            self.advance()
            right = self.parse_logical_and()
            left = BinaryExpr(BinaryOperator.LOGICAL_OR, left, right, span=self._span(left, right))
        return left

    def parse_logical_and(self) -> Expr:
        # logical_and ::= equality (LOGICAL_AND equality)*
        left = self.parse_equality()
        while self.check(TokenKind.LOGICAL_AND):
            self.advance()
            right = self.parse_equality()
            left = BinaryExpr(BinaryOperator.LOGICAL_AND, left, right, span=self._span(left, right))
        return left
    
    def parse_equality(self) -> Expr:
        # equality ::= relational ((EQUAL_EQUAL | NOT_EQUAL) relational)*
        left = self.parse_relational()
        
        while self.peek().kind in {TokenKind.EQUAL_EQUAL, TokenKind.NOT_EQUAL}:
            op_token = self.advance()
            op = BinaryOperator.EQUAL if op_token.kind == TokenKind.EQUAL_EQUAL else BinaryOperator.NOT_EQUAL
            right = self.parse_relational()
            left = BinaryExpr(op, left, right, span=self._span(left, right))
        return left
    
    def parse_relational(self) -> Expr:
        # relational ::= additive ((LESS | LESS_EQUAL | GREATER | GREATER_EQUAL) additive)*
        left = self.parse_additive()
        
        ops = {
            TokenKind.LESS: BinaryOperator.LESS,
            TokenKind.LESS_EQUAL: BinaryOperator.LESS_EQUAL,
            TokenKind.GREATER: BinaryOperator.GREATER,
            TokenKind.GREATER_EQUAL: BinaryOperator.GREATER_EQUAL,
        }
        
        while self.peek().kind in ops:
            op_token = self.advance()
            right = self.parse_additive()
            left = BinaryExpr(ops[op_token.kind], left, right, span=self._span(left, right))
        return left

    def parse_additive(self) -> Expr:
        # additive ::= multiplicative ((PLUS | MINUS) multiplicative)*
        left = self.parse_multiplicative()
        
        while self.peek().kind in {TokenKind.PLUS, TokenKind.MINUS}:
            op_token = self.advance()
            op = BinaryOperator.ADD if op_token.kind == TokenKind.PLUS else BinaryOperator.SUBTRACT
            right = self.parse_multiplicative()
            left = BinaryExpr(op, left, right, span=self._span(left, right))
        return left

    def parse_multiplicative(self) -> Expr:
        # multiplicative ::= unary ((STAR | SLASH | PERCENT) unary)*
        left = self.parse_unary()
        
        ops = {
            TokenKind.STAR: BinaryOperator.MULTIPLY,
            TokenKind.SLASH: BinaryOperator.DIVIDE,
            TokenKind.PERCENT: BinaryOperator.REMAINDER,
        }
        
        while self.peek().kind in ops:
            op_token = self.advance()
            right = self.parse_unary()
            left = BinaryExpr(ops[op_token.kind], left, right, span=self._span(left, right))
        return left
    
    def parse_unary(self) -> Expr:
        # unary ::= (LOGICAL_NOT | MINUS) unary | primary
        token = self.peek()
        
        if token.kind in {TokenKind.LOGICAL_NOT, TokenKind.MINUS}:
            self.advance()
            op = UnaryOperator.NOT if token.kind == TokenKind.LOGICAL_NOT else UnaryOperator.NEGATE
            
            # recursao para garantir a assiciatividade a direita
            operand = self.parse_unary()
            return UnaryExpr(op, operand, span=self._span(token, operand))
        return self.parse_primary()
            
    def parse_primary(self) -> Expr:
        """primary ::= LEFT_PAREN expression RIGHT_PAREN
          | IDENTIFIER (LEFT_PAREN arguments RIGHT_PAREN)?
          | INT_LITERAL
          | KW_TRUE
          | KW_FALSE
          """
        
        token = self.peek()
        
        if self.match(TokenKind.LEFT_PAREN):
            expr = self.parse_expression()
            end = self.expect(TokenKind.RIGHT_PAREN)
            
            try:
                expr.span = self._span(token, end)
            except AttributeError:
                object.__setattr__(expr, 'span', self._span(token, end))
            return expr
        
        elif self.check(TokenKind.IDENTIFIER):
            start = self.advance()
            if self.match(TokenKind.LEFT_PAREN):
                args = self.parse_arguments()
                end = self.expect(TokenKind.RIGHT_PAREN)
                return CallExpr(start.lexeme, args, span=self._span(start, end))
            return IdentifierExpr(start.lexeme, span=self._token_span(start))
            
        elif self.check(TokenKind.INT_LITERAL):
            start = self.advance()
            return IntLiteral(int(start.lexeme), span=self._token_span(start))
            
        elif self.check(TokenKind.KW_TRUE):
            start = self.advance()
            return BoolLiteral(True, span=self._token_span(start))
            
        elif self.check(TokenKind.KW_FALSE):
            start = self.advance()
            return BoolLiteral(False, span=self._token_span(start))
            
        else:
            raise ParserError(token, EXPRESSION_START)

    def parse_arguments(self) -> list[Expr]:
        # arguments ::= (expression (COMMA expression)*)?
        args = []
        
        if self.peek().kind in EXPRESSION_START:
            args.append(self.parse_expression())
            while self.match(TokenKind.COMMA):
                args.append(self.parse_expression())
                
        return args