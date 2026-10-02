"""
Executor unificado da suíte de testes do Wartales CAT Studio.
"""

import sys
import unittest
import os

DIRETORIO_PROJETO = os.path.dirname(os.path.abspath(__file__))
if DIRETORIO_PROJETO not in sys.path:
    sys.path.insert(0, DIRETORIO_PROJETO)


def executar_todos_testes():
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=os.path.join(DIRETORIO_PROJETO, "testes"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    resultado = runner.run(suite)
    if not resultado.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    executar_todos_testes()
