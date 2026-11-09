"""Testes locais da especificação Gold; a integração real é registrada pelo executor."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gold_dimensoes as g
import silver as s


class GoldDimensoesTests(unittest.TestCase):
    def test_exactly_six_dimensions_and_no_persistent_auxiliary_objects(self):
        self.assertEqual(len(g.SPECS),6)
        self.assertEqual(g.ddl().count('CREATE TABLE IF NOT EXISTS gold.'),6)
        self.assertNotIn('CREATE VIEW',g.ddl())
        self.assertNotIn('CREATE SEQUENCE',g.ddl())
        self.assertNotIn('fato_',g.ddl())

    def test_client_has_no_permanent_address(self):
        self.assertEqual([n for n,_ in g.fields('dim_clientes')],['cliente_sk','customer_unique_id','membro_tipo'])

    def test_location_is_exact_order_context_not_raw_geolocation(self):
        sql=g.source('dim_localizacao')
        self.assertIn('c.customer_id=o.customer_id',sql)
        self.assertNotIn('geolocation',sql)
        for transformation in ['lower(', 'upper(', 'trim(', 'unaccent(']:
            self.assertNotIn(transformation,g.ddl()+g.load())
        self.assertEqual(len(g.SPECS['dim_localizacao'][1]),3)

    def test_static_keys_are_deterministic_and_not_sequences(self):
        for name in g.SPECS:
            self.assertIn('row_number() OVER (ORDER BY',g.expected(name))
            self.assertEqual(g.fields(name)[0][1],'bigint')
            self.assertIn('ON CONFLICT',g.load())
        self.assertNotIn('DO UPDATE',g.load())
        self.assertNotIn('DELETE FROM',g.load())

    def test_special_members_have_null_natural_values_and_no_fake_day(self):
        for name in g.SPECS:
            sql=g.expected(name)
            self.assertIn('-1::bigint',sql)
            self.assertIn('-2::bigint',sql)
            self.assertNotIn('nao_aplicavel',sql)
        self.assertIn("NULL::date",g.expected('dim_calendario'))
        self.assertNotIn('1900',g.expected('dim_calendario'))

    def test_calendar_covers_only_documented_roles_without_timezone(self):
        self.assertEqual(len(g.ROLES),6)
        self.assertIn(('items','shipping_limit_date'),g.ROLES)
        self.assertNotIn('review_creation_date',g.calendar_days())
        self.assertNotIn('timestamptz',g.source('dim_calendario'))
        self.assertIn('inicio+g',g.source('dim_calendario'))

    def test_guard_keeps_legacy_file_and_limits_gold(self):
        self.assertNotIn("'gold'",s.guard_sql())
        self.assertIn("'gold'",g.guard())
        self.assertIn("AND NOT ((n.nspname='silver'",g.guard())
        self.assertIn("OR (n.nspname='gold'",g.guard())
        self.assertIn('Schema gold preexistente não reconhecido',g.guard())
        self.assertIn("AND contype<>'n')<>3",g.guard())

    def test_sql_artifacts_match_generator(self):
        self.assertEqual((s.ROOT/'sql/gold/001_dimensoes.sql').read_text(encoding='utf-8'),g.ddl())
        self.assertEqual((s.ROOT/'sql/gold/002_carga_dimensoes.sql').read_text(encoding='utf-8'),g.load())
        self.assertEqual((s.ROOT/'sql/validacoes/gold_dimensoes.sql').read_text(encoding='utf-8'),g.validation()+g.observations())

    def test_resolution_and_unknown_are_distinct_from_not_defined(self):
        self.assertIn("p.payment_type='not_defined'",g.validation())
        self.assertIn("membro_tipo<>'regular'",g.validation())
        self.assertIn('WHEN c.customer_id IS NULL THEN -2',g.resolution_sources()['pedidos_cliente'][1])
        self.assertIn('WHEN c.customer_unique_id IS NULL THEN -1',g.resolution_sources()['pedidos_cliente'][1])
        self.assertIn('EXCEPT ALL',g.validation())

    def test_constraint_failures_are_expected_not_swallowed_generically(self):
        self.assertIn('WHEN unique_violation THEN',g.constraint_tests())
        self.assertIn('WHEN check_violation THEN',g.constraint_tests())
        self.assertNotIn('WHEN OTHERS',g.constraint_tests())


if __name__=='__main__':
    unittest.main()
