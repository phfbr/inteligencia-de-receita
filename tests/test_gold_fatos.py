"""Contratos locais da etapa 4C; testes PostgreSQL são executados pelo orquestrador."""
import sys
import json
import copy
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import gold_fatos as f
import gold_dimensoes as d
import silver as s


class GoldFatosTests(unittest.TestCase):
    def test_three_natural_grains_without_surrogate_fact_keys(self):
        self.assertEqual({n:pk for n,(_,pk) in f.SPECS.items()},
            dict(fato_pedidos=('order_id',),fato_itens_pedido=('order_id','order_item_id'),
                 fato_pagamentos=('order_id','payment_sequential')))
        self.assertEqual(f.ddl().count('CREATE TABLE IF NOT EXISTS gold.'),3)
        self.assertNotIn('GENERATED',f.ddl())

    def test_only_dimension_foreign_keys_in_approved_roles(self):
        self.assertEqual([len(f.fks(n)) for n in f.SPECS],[7,6,4])
        self.assertEqual(sum(len(f.fks(n)) for n in f.SPECS),17)
        for name in f.SPECS:
            for _,target,_ in f.fks(name):self.assertIn(target,d.SPECS)
        self.assertIn('data_limite_envio_sk',[n for n,_,_ in f.fks('fato_itens_pedido')])
        self.assertNotIn('forma_pagamento_sk',[n for n,_,_ in f.fks('fato_pedidos')])

    def test_exact_money_and_nonadditive_installments(self):
        self.assertNotIn('price',dict(f.fields('fato_pedidos')))
        self.assertEqual(dict(f.fields('fato_itens_pedido'))['price'],'numeric')
        self.assertEqual(dict(f.fields('fato_itens_pedido'))['freight_value'],'numeric')
        self.assertEqual(dict(f.fields('fato_pagamentos'))['payment_value'],'numeric')
        self.assertEqual(dict(f.fields('fato_pagamentos'))['payment_installments'],'numeric')
        self.assertNotIn('sum(payment_installments)',f.observations())

    def test_identifiers_remain_text_and_timestamps_keep_source_type(self):
        for name in f.SPECS:
            for col,kind in f.fields(name):
                if col.endswith('_id') or col=='payment_sequential':self.assertEqual(kind,'text')
                if col in s.DATES:self.assertEqual(kind,'timestamp without time zone')

    def test_no_detailed_item_payment_join_or_status_filter(self):
        self.assertNotIn('olist_order_payments',f.expected('fato_itens_pedido'))
        self.assertNotIn('olist_order_items',f.expected('fato_pagamentos'))
        self.assertNotIn("'delivered'",f.load())
        for name in f.SPECS:
            self.assertNotIn('INNER JOIN',f.expected(name))
            self.assertNotIn('geolocation',f.expected(name))

    def test_customer_location_resolution_not_permanent_customer_address(self):
        sql=f.expected('fato_itens_pedido')
        self.assertIn('c.customer_id=o.customer_id',sql)
        self.assertIn('dl.customer_zip_code_prefix=c.customer_zip_code_prefix',sql)
        self.assertNotIn('dc.localizacao',sql)
        self.assertIn('WHEN o.order_id IS NULL THEN -2',sql)
        self.assertIn('WHEN o.customer_id IS NULL THEN -1',sql)
        self.assertIn('WHEN c.customer_id IS NULL THEN -2',sql)

    def test_unknown_dates_do_not_fabricate_timestamps(self):
        sql=f.expected('fato_pedidos')
        self.assertIn('WHEN o."order_delivered_customer_date" IS NULL THEN -1',sql)
        self.assertNotIn('1900',sql)
        self.assertNotIn('CURRENT_DATE',sql)
        self.assertNotIn('AT TIME ZONE',sql)

    def test_independent_reconciliation_preserves_orders_without_children(self):
        sql=f.reconciliation('gold')
        self.assertEqual(sql.count('GROUP BY order_id'),2)
        self.assertIn('LEFT JOIN i',sql)
        self.assertIn('LEFT JOIN p',sql)
        self.assertIn('THEN NULL ELSE p.valor-i.preco-i.frete',sql)
        self.assertIn('EXCEPT ALL',f.validation())

    def test_ddl_has_no_cascades_fact_fact_relationships_or_dimension_writes(self):
        ddl=f.ddl()
        self.assertEqual(ddl.count('FOREIGN KEY ('),17)
        self.assertNotIn('REFERENCES gold."fato_',ddl)
        self.assertNotIn('CASCADE',ddl)
        self.assertNotIn('CREATE SCHEMA',ddl)
        self.assertNotIn('DROP ',ddl)
        self.assertNotIn('INSERT INTO gold."dim_',f.load())
        self.assertNotIn('DO UPDATE',f.load())

    def test_guard_extension_is_local_fail_closed_and_preserves_old_guards(self):
        self.assertNotIn("'fato_pedidos'",d.guard())
        self.assertIn("'fato_pedidos'",f.guard())
        self.assertIn('FK ausente ou incompatível',f.guard())
        self.assertIn("k.confupdtype='a' AND k.confdeltype='a'",f.guard())
        self.assertIn('NOT k.condeferrable',f.guard())

    def test_constraint_tests_expect_only_specific_failures(self):
        sql=f.constraint_tests()
        self.assertEqual(sql.count('WHEN foreign_key_violation'),17)
        self.assertEqual(sql.count('WHEN unique_violation'),3)
        self.assertEqual(sql.count('WHEN not_null_violation'),3)
        self.assertNotIn('WHEN OTHERS',sql)

    def test_checked_in_sql_matches_reviewable_generator(self):
        self.assertEqual((s.ROOT/'sql/gold/003_fatos.sql').read_text(encoding='utf-8'),f.ddl())
        self.assertEqual((s.ROOT/'sql/gold/004_carga_fatos.sql').read_text(encoding='utf-8'),f.load())
        self.assertEqual((s.ROOT/'sql/validacoes/gold_fatos.sql').read_text(encoding='utf-8'),f.validation()+f.observations())

    def test_approved_dimension_catalog_cannot_drift(self):
        approved=json.loads((f.DIM_EVIDENCE/'resultado.json').read_text(encoding='utf-8'))
        catalog=json.loads((f.DIM_EVIDENCE/'catalogo.json').read_text(encoding='utf-8'))
        rows=copy.deepcopy(approved['after'])
        rows += [dict(dimension_columns=copy.deepcopy(catalog[1]['columns'])),
                 dict(dimension_constraints=copy.deepcopy(catalog[2]['constraints']))]
        f.check_dim_reference(rows,approved,catalog)
        rows[-2]['dimension_columns'][0]['type']='double precision'
        with self.assertRaises(s.SilverError):f.check_dim_reference(rows,approved,catalog)


if __name__=='__main__':
    unittest.main()
