"""Construa um CFG auxiliar por função, preservando os nós da AST."""

from __future__ import annotations

import load_previous  # Disponibiliza os módulos das etapas anteriores.

from ast_nodes import Block, FunctionDecl, IfStmt, Stmt, WhileStmt
from cfg import BlockId, CFG, Jump, ScopeExit


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
        for stmt in block.statemens:
            if current is None:
                break
            current = self._build_statement(stmt, current)

        if current is not None:
            scope = block.metadata["scope"]
            self.cfg.blocks[current].operations.append(ScopeExit(scope))


    def _build_statement(self, statement: Stmt, current: BlockId) -> BlockId | None:
        """TODO: incorpore um comando ao CFG e devolva sua continuação normal."""

        

        raise NotImplementedError("implemente CFGBuilder._build_statement")

    def _build_if(self, statement: IfStmt, current: BlockId) -> BlockId | None:
        """TODO: construa o fluxo da condicional e devolva sua continuação."""

        raise NotImplementedError("implemente CFGBuilder._build_if")

    def _build_while(self, statement: WhileStmt, current: BlockId) -> BlockId | None:
        """TODO: construa o fluxo do laço e devolva sua continuação."""

        raise NotImplementedError("implemente CFGBuilder._build_while")
