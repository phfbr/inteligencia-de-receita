"""Casos sintéticos de parser e preservação; não representam dados da Olist."""
import importlib.util
import tempfile
import unittest
from collections import Counter
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'profiling', Path(__file__).resolve().parents[1] / 'scripts/profiling.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ProfilingTests(unittest.TestCase):
    def test_csv_records_duplicates_and_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'customers.csv'
            content = (b'customer_id,customer_unique_id,note\n'
                       b'a,u,"first\nsecond"\n'
                       b'a,u,"first\nsecond"\n'
                       b'b,,empty\n'
                       b'bad,row\n')
            path.write_bytes(content)
            report, retained = p.profile(path, 'customers')
            self.assertEqual(report['rows'], 4)
            self.assertEqual(report['exact_duplicate_excess'], 1)
            self.assertEqual(report['malformed_rows'], 1)
            self.assertEqual(report['columns']['customer_unique_id']['empty'], 1)
            self.assertFalse(report['keys']['customer_id']['unique_nonnull_observed'])
            self.assertEqual(len(retained), 3)
            self.assertEqual(path.read_bytes(), content)

    def test_invalid_values_are_not_silently_numeric(self):
        report = p.column_profile('price', Counter({'0': 1, '-2': 1, 'bad': 1, '': 1}), 4)
        self.assertEqual(report['numeric_invalid'], 1)
        self.assertEqual(report['numeric_distribution']['negative'], 1)
        self.assertEqual(report['empty'], 1)

    def test_dates_and_percentiles(self):
        report = p.column_profile('order_approved_at', Counter({'2020-01-01': 1, 'bad': 2}), 3)
        self.assertEqual(report['date_invalid'], 2)
        self.assertEqual(p.distribution([1, 2, 3, 4])['median'], 2.5)

    def test_fanout_customer_mapping_and_decimal_reconciliation(self):
        order = dict(order_id='o', customer_id='c', order_status='created',
                     order_purchase_timestamp='2020-01-01', order_approved_at='',
                     order_delivered_carrier_date='', order_delivered_customer_date='')
        data = dict(orders=[order], customers=[dict(customer_id='c', customer_unique_id='u')],
                    items=[dict(order_id='o', price='0.10', freight_value='0.00')] * 3,
                    payments=[dict(order_id='o', payment_value='0.15')] * 2)
        report = p.commercial(data)
        self.assertEqual(report['inner_join_rows_orders_items_payments'], 6)
        self.assertEqual(report['orders_with_both_multiple'], 1)
        self.assertEqual(report['orders_without_unambiguous_customer_mapping'], 0)
        self.assertEqual(report['reconciliation']['payment_minus_items_and_freight']['zero'], 1)


if __name__ == '__main__':
    unittest.main()
