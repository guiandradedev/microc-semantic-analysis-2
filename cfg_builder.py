"""Construa um CFG auxiliar por função, preservando os nós da AST."""

from __future__ import annotations

import load_previous  # Disponibiliza os módulos das etapas anteriores.

from ast_nodes import (
    Assignment,
    Block,
    BoolLiteral,
    CallStmt,
    FunctionDecl,
    IfStmt,
    PrintStmt,
    ReturnStmt,
    Stmt,
    VarDecl,
    WhileStmt,
)
from cfg import BlockId, Branch, CFG, Jump, Return, ScopeExit

class CFGBuilder:
    def build(self, function: FunctionDecl) -> CFG:
        self.cfg = CFG(function)
        body_entry = self.cfg.new_block()
        self.cfg.terminate(self.cfg.entry, Jump(body_entry.id))
        continuation = self._build_block(function.body, body_entry.id)
        if continuation is not None:
            self.cfg.terminate(continuation, Jump(self.cfg.fallthrough_exit))
        return self.cfg

    def _build_block(self, block: Block, current: BlockId) -> BlockId | None:
        """Percorra um bloco da AST e devolva sua continuação normal.

        `current` identifica um bloco básico aberto. Comandos sequenciais
        permanecem nele. Comandos de controle podem mudar a continuação.
        None indica que os caminhos deste bloco não alcançam o próximo comando.
        """
        for stmt in block.statements:
            if current is None:
                break
            current = self._build_statement(stmt, current)

        if current is not None:
            scope = block.metadata["scope"]
            self.cfg.blocks[current].operations.append(ScopeExit(scope))
            
        return current


    def _build_statement(self, statement: Stmt, current: BlockId) -> BlockId | None:
        """TODO: incorpore um comando ao CFG e devolva sua continuação normal."""
        
        if isinstance(statement, (VarDecl, Assignment, PrintStmt, CallStmt)):
            self.cfg.blocks[current].operations.append(statement)
            return current
            
        elif isinstance(statement, IfStmt):
            return self._build_if(statement, current)
            
        elif isinstance(statement, WhileStmt):
            return self._build_while(statement, current)
            
        elif isinstance(statement, Block):
            return self._build_block(statement, current)
            
        elif isinstance(statement, ReturnStmt):
            self.cfg.terminate(current, Return(statement))
            return None
        raise TypeError(f"comando desconhecido: {type(statement).__name__}")

    def _build_if(self, statement: IfStmt, current: BlockId) -> BlockId | None:
        # Cria os blocos iniciais para ramos verdadeiros e falsos
        true_block = self.cfg.new_block()
        false_block = self.cfg.new_block()
        
        # fecha o bloco atual com condiciontal 
        self.cfg.terminate(current, Branch(statement.condition, true_block.id, false_block.id))
        
        # Cria o ramo verdadeiro
        end_true = self._build_block(statement.then_block, true_block.id)
        
        # constroi o ramo false se existir 
        if statement.else_block is not None:
            end_false = self._build_block(statement.else_block, false_block.id)
        else:
            # se não existir, cria um bloco vazio para o else
            end_false = false_block.id 
            
        # caso ambos terminarem, derem um return
        if end_true is None and end_false is None:
            return None

        # Cria o bloco de juncao para ambos os ramos
        merge_block = self.cfg.new_block()
        if end_true is not None:
            self.cfg.terminate(end_true, Jump(merge_block.id))
        if end_false is not None:
            self.cfg.terminate(end_false, Jump(merge_block.id))
            
        return merge_block.id

    def _build_while(self, statement: WhileStmt, current: BlockId) -> BlockId | None:
        """TODO: construa o fluxo do laço e devolva sua continuação."""
        test_block = self.cfg.new_block()
        body_block = self.cfg.new_block()

        self.cfg.terminate(current, Jump(test_block.id))

        if isinstance(statement.condition, BoolLiteral) and statement.condition.value is True:
            self.cfg.terminate(test_block.id, Branch(statement.condition, body_block.id, body_block.id))
            
            end_block = self._build_block(statement.body, body_block.id)
            
            if end_block is not None:
                self.cfg.terminate(end_block, Jump(test_block.id))
            return None
    
        exit_block = self.cfg.new_block()
        self.cfg.terminate(test_block.id, Branch(statement.condition, body_block.id, exit_block.id))
        
        end_body = self._build_block(statement.body, body_block.id)
        if end_body is not None:
            self.cfg.terminate(end_body, Jump(test_block.id))
        
        return exit_block.id