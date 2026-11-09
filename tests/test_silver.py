"""Testes locais de preservação e segurança; não simulam uma carga PostgreSQL real."""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import silver as s
import concluir_silver as completion


def fixture(root):
    bronze = root / 'bronze'
    bronze.mkdir()
    baseline = {'datasets': {}}
    for entity, filename in s.FILES.items():
        values = []
        for name, kind in s.columns(entity):
            values.append('2017-01-01 12:00:00' if kind.startswith('timestamp') else
                          '0.10' if kind == 'numeric' else 'id')
        if entity == 'customers':
            values[2] = '00123'
        if entity == 'reviews':
            values[4] = 'Comentário\ncom tab\t e barra \\N'
        if entity == 'products':
            values[1] = 'sem_traducao'
            values[2] = ''
        if entity == 'payments':
            values[-1] = 'valor_invalido'
        rows = [values] * (2 if entity in ('geolocation', 'reviews') else 1)
        path = bronze / filename
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(s.HEADERS[entity].split())
            writer.writerows(rows)
        baseline['datasets'][entity] = {'rows': len(rows), 'sha256': s.sha256(path)}
    return bronze, baseline


class SilverTests(unittest.TestCase):
    def test_completion_refuses_other_database(self):
        with patch.dict(os.environ, {'PGDATABASE': 'outro', 'OLIST_PROJECT_DATABASE': 'outro'}):
            with patch.object(completion, 'run_sql') as run:
                with self.assertRaises(s.SilverError):
                    completion.inspect_and_identify(Path('.'))
                run.assert_not_called()

    def test_completion_does_not_adopt_existing_objects(self):
        row = dict(database=completion.DATABASE, owner='owner', user='owner', marker_missing=True,
                   marker_matches=False, user_relations=[dict(name='preexistente')])
        with patch.dict(os.environ, {'PGDATABASE': completion.DATABASE, 'OLIST_PROJECT_DATABASE': completion.DATABASE}):
            with patch.object(completion, 'run_sql', return_value=[row]) as run:
                with self.assertRaises(s.SilverError):
                    completion.inspect_and_identify(Path('.'))
                self.assertEqual(run.call_count, 1)

    def test_completion_identifies_only_empty_authorized_database(self):
        row = dict(database=completion.DATABASE, owner='owner', user='owner', marker_missing=True,
                   marker_matches=False, user_relations=[])
        with patch.dict(os.environ, {'PGDATABASE': completion.DATABASE, 'OLIST_PROJECT_DATABASE': completion.DATABASE}):
            with patch.object(completion, 'run_sql', side_effect=[[row], []]) as run, patch.object(s, 'preflight', return_value=[]):
                result = completion.inspect_and_identify(Path('.'))
                self.assertTrue(result['database_comment_initialized'])
                first, second = (call.args[2] for call in run.call_args_list)
                self.assertIn('BEGIN READ ONLY;', first)
                self.assertIn('COMMENT ON DATABASE "inteligencia_receita_db"', second)
                self.assertNotIn('DELETE FROM', second)
                self.assertNotIn('DROP ', second)

    def test_completion_preserves_existing_database_marker(self):
        row = dict(database=completion.DATABASE, owner='owner', user='owner', marker_missing=False,
                   marker_matches=True, user_relations=[])
        with patch.dict(os.environ, {'PGDATABASE': completion.DATABASE, 'OLIST_PROJECT_DATABASE': completion.DATABASE}):
            with patch.object(completion, 'run_sql', return_value=[row]) as run, patch.object(s, 'preflight', return_value=[]):
                result = completion.inspect_and_identify(Path('.'))
                self.assertFalse(result['database_comment_initialized'])
                self.assertEqual(run.call_count, 1)

    def test_identifiers_and_exact_types(self):
        self.assertEqual(dict(s.columns('items'))['order_item_id'], 'text')
        self.assertEqual(dict(s.columns('payments'))['payment_sequential'], 'text')
        self.assertEqual(dict(s.columns('customers'))['customer_zip_code_prefix'], 'text')
        self.assertEqual(s.convert('00123', 'text'), ('00123', None))
        self.assertEqual(s.convert('0.10', 'numeric'), (Decimal('0.10'), None))
        self.assertEqual(s.convert('', 'text'), (None, None))
        self.assertEqual(s.convert('  ', 'text'), ('  ', None))
        self.assertEqual(s.convert('NULL', 'text'), ('NULL', None))

    def test_timestamps_are_not_shifted_or_rounded(self):
        self.assertEqual(s.convert('2017-01-01 23:59:59.123456', 'timestamp without time zone'),
                         (datetime(2017, 1, 1, 23, 59, 59, 123456), None))
        for value in ['2017-01-01 12:00:00Z', '2017-01-01 12:00:00.1234567', '2017-02-30 12:00:00']:
            parsed, error = s.convert(value, 'timestamp without time zone')
            self.assertIsNone(parsed)
            self.assertIsNotNone(error)

    def test_copy_special_characters_and_null_are_distinct(self):
        self.assertEqual(s.copy_text(None), r'\N')
        self.assertEqual(s.copy_text(r'\N'), r'\\N')
        self.assertEqual(s.copy_text('a\tb\nc\r\\.'), r'a\tb\nc\r\\.')
        self.assertEqual(s.copy_text(Decimal('123.45')), '123.45')

    def test_duplicates_invalid_values_and_original_text_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bronze, baseline = fixture(root)
            stats = s.source_scan(bronze, baseline, root)
            self.assertEqual(stats['geolocation']['rows'], 2)
            self.assertEqual(stats['reviews']['keys']['review_id']['duplicate_excess'], 1)
            self.assertEqual(stats['payments']['conversion_errors']['payment_value'], 1)
            self.assertEqual(stats['payments']['nulls']['payment_value'], 1)
            self.assertEqual(stats['products']['nulls']['product_name_lenght'], 1)
            self.assertEqual(stats['products']['references']['product_category_name->translation.product_category_name'], 1)
            copy = (root / 'payments.copy').read_text(encoding='utf-8')
            self.assertIn('valor_invalido', copy)
            self.assertIn('invalid_numeric', copy)
            self.assertIn('00123', (root / 'customers.copy').read_text(encoding='utf-8'))
            self.assertEqual(stats['items']['numeric_sums']['price'], '0.10')
            for entity, filename in s.FILES.items():
                self.assertEqual(s.sha256(bronze / filename), baseline['datasets'][entity]['sha256'])

    def test_source_change_blocks_without_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            bronze, baseline = fixture(Path(folder))
            with (bronze / s.FILES['orders']).open('a') as stream:
                stream.write('changed')
            with self.assertRaises(s.SilverError):
                s.source_scan(bronze, baseline)

    def test_generated_sql_is_reviewable_and_matches_checked_in_files(self):
        self.assertEqual((s.ROOT / 'sql/silver/001_estrutura.sql').read_text(encoding='utf-8'), s.ddl_sql())
        self.assertEqual((s.ROOT / 'sql/validacoes/silver.sql').read_text(encoding='utf-8'), s.observation_sql())
        self.assertEqual(s.ddl_sql().count('CREATE TABLE IF NOT EXISTS'), 9)
        self.assertNotIn('DROP ', s.ddl_sql())
        self.assertIn('Exclusividade do projeto não comprovada', s.guard_sql())
        self.assertIn('IS DISTINCT FROM current_setting', s.guard_sql())

    def test_pg18_not_null_catalog_entries_do_not_mask_other_constraints(self):
        self.assertEqual(s.guard_sql().count("AND contype <> 'n') <> 1"), 9)
        self.assertEqual(s.guard_sql().count("AND contype='p'"), 9)
        self.assertIn("'required',a.attnotnull", s.guard_sql())

    def test_missing_environment_never_invokes_psql(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            root = Path(folder)
            bronze, baseline = fixture(root)
            manifest = root / 'baseline.json'
            manifest.write_text(json.dumps(baseline))
            with patch.object(s, 'run_psql') as run:
                result = s.execute('prepare', bronze, manifest, root / 'output')
                self.assertEqual(result['status'], 'blocked')
                self.assertFalse(result['database_load_completed'])
                run.assert_not_called()

    def test_private_errors_are_not_logged(self):
        for prefix in ('ERROR', 'ERRO'):
            fake = subprocess.CompletedProcess([], 1, stdout='', stderr=f'password=canary-secret\n{prefix}: 28P01\n')
            with patch.object(s, 'psql_path', return_value='psql'), patch.object(s.subprocess, 'run', return_value=fake):
                with self.assertRaises(s.SilverError) as caught:
                    s.run_psql(Path('dummy.sql'))
                self.assertNotIn('canary-secret', str(caught.exception))
                self.assertIn('28P01', str(caught.exception))

    def test_atomic_replace_and_failure_before_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bronze, baseline = fixture(root)
            stats = s.source_scan(bronze, baseline, root)
            plan = root / 'plan.sql'
            s.write_load(plan, stats, root, inject_failure=True)
            text = plan.read_text(encoding='utf-8')
            self.assertEqual(text.count('DELETE FROM silver.'), 9)
            self.assertEqual(text.count(' FROM STDIN;'), 9)
            self.assertLess(text.index('BEGIN;'), text.index('DO $guard$'))
            self.assertLess(text.index('DO $guard$'), text.index('DELETE FROM'))
            self.assertLess(text.index('SELECT 1/0;'), text.index('COMMIT;'))
            self.assertNotIn('TRUNCATE ', text)
            self.assertIn('string_agg(', text)
            self.assertIn('Integridade difere da Bronze', text)


@unittest.skipUnless(os.environ.get('OLIST_RUN_DB_TESTS') == '1',
                     'Integração pendente: exige conexão exclusiva configurada e OLIST_RUN_DB_TESTS=1.')
class SilverIntegrationTests(unittest.TestCase):
    def test_real_load_reexecution_and_rollback(self):
        self.assertFalse(s.environment_status()['blockers'])
        baseline = s.ROOT / 'docs/qualidade/profiling/resultados.json'
        evidence = os.environ.get('OLIST_DB_EVIDENCE_DIR')
        context = nullcontext(evidence) if evidence else tempfile.TemporaryDirectory()
        with context as folder:
            output = Path(folder)
            first = s.execute('load', s.ROOT / 'data/bronze', baseline, output / 'first')
            self.assertEqual(first['status'], 'committed')
            second = s.execute('load', s.ROOT / 'data/bronze', baseline, output / 'second')
            self.assertEqual(second['status'], 'committed')
            self.assertEqual(first['database_results'], second['database_results'])
            failed = s.execute('load', s.ROOT / 'data/bronze', baseline, output / 'rollback', inject_failure=True)
            self.assertEqual(failed['status'], 'failed')
            self.assertFalse(failed['database_load_completed'])
            self.assertTrue(any('SQLSTATE 22012' in error for error in failed['errors']),
                            'Rollback só é confirmado para a falha deliberada de divisão por zero.')
            verified = s.execute('verify', s.ROOT / 'data/bronze', baseline, output / 'verify')
            self.assertEqual(verified['status'], 'verified_readonly')
            self.assertEqual(second['database_results'], verified['database_results'])


if __name__ == '__main__':
    unittest.main()
