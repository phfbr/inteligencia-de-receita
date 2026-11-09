"""Proteções do executor analítico; não requer conexão nem modifica o banco."""
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validacao_analitica as a


class ContratoLeitura(unittest.TestCase):
    def test_bloqueia_escrita_e_multiplas_instrucoes(self):
        for sql in ['DELETE FROM gold.fato_pedidos', 'WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x', 'SELECT 1; DELETE FROM t', 'SELECT * INTO t FROM x']:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                a.safe(sql)

    def test_catalogo_inteiro_somente_leitura(self):
        for query in a.queries().values():
            a.safe(query)

    def test_reconciliacao_detecta_diferenca(self):
        # Transporte preserva centavos mesmo além da precisão de um float.
        result = SimpleNamespace(returncode=0, stdout='t\n{"valor":9007199254740992.01}\n', stderr='')
        with patch.object(a.s, 'psql_path', return_value='psql'), patch.object(a.subprocess, 'run', return_value=result):
            rows = a.run_sql(Path('consulta.sql'))
        self.assertEqual(rows[0]['valor'], Decimal('9007199254740992.01'))


if __name__ == '__main__':
    target = a.s.ROOT / 'docs/qualidade/etapa5_validacao_analitica/testes_unitarios.log'
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('w', encoding='utf-8') as log:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ContratoLeitura)
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    print(f'{result.testsRun} testes; sucesso={result.wasSuccessful()}; log={target}')
    sys.exit(0 if result.wasSuccessful() else 1)
