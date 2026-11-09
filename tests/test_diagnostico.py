"""Casos sintéticos para regras diagnósticas, sem representar dados observados."""
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import diagnostico as d


def order(oid, cid, state='delivered', stamp='2020-01-01 12:00:00'):
    return dict(order_id=oid, customer_id=cid, order_status=state,
                order_purchase_timestamp=stamp, order_approved_at='',
                order_delivered_carrier_date='', order_delivered_customer_date='',
                order_estimated_delivery_date='2020-01-10 00:00:00')


def dataset():
    return dict(orders=[order('a', 'c1'), order('b', 'c2', 'canceled'),
                        order('c', 'c3', stamp='2020-01-02 12:00:00')],
                customers=[dict(customer_id=f'c{i}', customer_unique_id='u') for i in (1, 2, 3)],
                items=[dict(order_id='a', order_item_id=str(i), price='0.10', freight_value='0')
                       for i in (1, 2, 3)],
                payments=[dict(order_id='a', payment_sequential=str(i), payment_value='0.15')
                          for i in (1, 2)])


class DiagnosticTests(unittest.TestCase):
    def test_independent_aggregation_and_missing_status(self):
        report, details = d.analyze(dataset())
        self.assertEqual(report['reconciliation']['exact_zero'], 1)
        self.assertEqual(report['reconciliation']['divergent'], 0)
        self.assertEqual(report['status']['canceled']['without_items'], 1)
        self.assertEqual(report['missing']['without_either'], 2)
        self.assertEqual(len(details['pedidos_sem_itens_ou_pagamentos']), 2)

    def test_strict_decimal_threshold_and_sign(self):
        data = dataset()
        data['payments'][0]['payment_value'] = '0.16'
        report, _ = d.analyze(data)
        self.assertEqual(report['reconciliation']['divergent'], 0)
        self.assertEqual(report['reconciliation']['nonzero_at_most_one_cent'], 1)
        data['payments'][0]['payment_value'] = '0.13'
        report, rows = d.analyze(data)
        self.assertEqual(report['reconciliation']['negative'], 1)
        self.assertEqual(rows['divergencias'][0]['delta'], Decimal('-0.02'))
        self.assertEqual(d.magnitude(Decimal('0.10')), '(0.01,0.10]')
        self.assertEqual(d.magnitude(Decimal('100.01')), '>100')

    def test_simultaneous_and_later_orders(self):
        report, _ = d.analyze(dataset())
        c = report['customers']
        self.assertEqual(c['multiple_order_customers'], 1)
        self.assertEqual(c['same_timestamp_customers'], 1)
        self.assertEqual(c['equal_timestamp_unordered_pairs'], 1)
        self.assertEqual(c['adjacent_timing']['positive_at_most_24h'], 1)
        self.assertEqual(c['at_least_two_delivered'], 1)
        self.assertEqual(c['status']['canceled']['customers_with_status'], 1)

    def test_duplicates_fail_without_deduplication(self):
        data = dataset()
        data['items'].append(data['items'][0].copy())
        with self.assertRaisesRegex(ValueError, 'Chave ambígua'):
            d.analyze(data)

    def test_orphan_is_reported_and_not_removed(self):
        data = dataset()
        data['payments'].append(dict(order_id='unknown', payment_sequential='1', payment_value='2'))
        report, _ = d.analyze(data)
        self.assertEqual(report['references']['payments.order_id']['orphan_rows'], 1)
        self.assertEqual(len(data['payments']), 3)

    def test_invalid_money_fails_explicitly(self):
        data = dataset()
        data['payments'][0]['payment_value'] = 'NaN'
        with self.assertRaisesRegex(ValueError, 'não finito'):
            d.analyze(data)


if __name__ == '__main__':
    unittest.main()
