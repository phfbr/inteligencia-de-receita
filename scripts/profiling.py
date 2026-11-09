"""Profiling somente leitura da Bronze, sem pacotes externos. Python >= 3.10."""
import argparse
import csv
import hashlib
import json
import logging
import math
import platform
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

FILES = {
    'customers': 'olist_customers_dataset.csv',
    'geolocation': 'olist_geolocation_dataset.csv',
    'orders': 'olist_orders_dataset.csv',
    'items': 'olist_order_items_dataset.csv',
    'payments': 'olist_order_payments_dataset.csv',
    'reviews': 'olist_order_reviews_dataset.csv',
    'products': 'olist_products_dataset.csv',
    'sellers': 'olist_sellers_dataset.csv',
    'translation': 'product_category_name_translation.csv',
}
KEYS = {
    'customers': [('customer_id',), ('customer_unique_id',)],
    'orders': [('order_id',), ('customer_id',)],
    'items': [('order_id', 'order_item_id')],
    'payments': [('order_id', 'payment_sequential')],
    'reviews': [('review_id',), ('order_id',), ('review_id', 'order_id')],
    'products': [('product_id',)], 'sellers': [('seller_id',)],
    'translation': [('product_category_name',)],
    'geolocation': [('geolocation_zip_code_prefix',)],
}
NUMERIC = {
    'order_item_id', 'price', 'freight_value', 'payment_sequential',
    'payment_installments', 'payment_value', 'review_score',
    'product_name_lenght', 'product_description_lenght', 'product_photos_qty',
    'product_weight_g', 'product_length_cm', 'product_height_cm', 'product_width_cm',
    'geolocation_lat', 'geolocation_lng',
}
DATES = {
    'order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_date',
    'order_delivered_customer_date', 'order_estimated_delivery_date',
    'shipping_limit_date', 'review_creation_date', 'review_answer_timestamp',
}


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def distribution(values):
    values = sorted(values)
    if not values:
        return {'count': 0}
    def quantile(p):
        x = (len(values) - 1) * p
        a = int(x)
        return values[a] + (values[min(a + 1, len(values) - 1)] - values[a]) * (x - a)
    return dict(count=len(values), min=values[0], max=values[-1],
                mean=statistics.fmean(values), p25=quantile(.25),
                median=quantile(.5), p75=quantile(.75), p95=quantile(.95),
                negative=sum(v < 0 for v in values), zero=values.count(0))


def column_profile(name, counter, count):
    missing = counter.get('', 0)
    whitespace = sum(n for v, n in counter.items() if v and not v.strip())
    nonempty = {v: n for v, n in counter.items() if v != ''}
    result = dict(empty=missing, empty_pct=100 * missing / count if count else None,
                  whitespace_only=whitespace, distinct_nonempty=len(nonempty))
    parsed = []
    invalid = 0
    integers = True
    for value, freq in nonempty.items():
        try:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError('non-finite')
            integers = integers and number.is_integer()
            if name in NUMERIC:
                parsed.extend([number] * freq)
        except ValueError:
            invalid += freq
    result['inferred_type'] = ('empty' if not nonempty else
                               'text' if invalid else 'integer' if integers else 'decimal')
    # IDs e CEPs permanecem texto na origem, mesmo quando parecem números.
    result['identifier_semantics'] = name.endswith('_id') or 'zip_code' in name
    if name in NUMERIC:
        result['numeric_invalid'] = invalid
        result['numeric_distribution'] = distribution(parsed)
    if name in DATES:
        valid = []
        errors = 0
        for value, freq in nonempty.items():
            try:
                valid.append(datetime.fromisoformat(value))
            except ValueError:
                errors += freq
        result['date_invalid'] = errors
        result['date_min'] = min(valid).isoformat() if valid else None
        result['date_max'] = max(valid).isoformat() if valid else None
        result['inferred_type'] = 'datetime' if valid and not errors else result['inferred_type']
    if name in {'order_status', 'payment_type', 'payment_installments', 'review_score',
                'product_category_name', 'customer_state', 'seller_state'}:
        result['frequencies'] = dict(sorted(counter.items(), key=lambda x: (-x[1], x[0])))
    return result


def profile(path, entity):
    before = sha256(path)
    columns = None
    counts = {}
    seen = set()
    key_counts = {key: Counter() for key in KEYS[entity]}
    key_nulls = Counter()
    retained = []
    rows = malformed = duplicates = 0
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream, strict=True)
        columns = next(reader)
        if len(columns) != len(set(columns)):
            raise ValueError(f'Cabeçalho duplicado: {path.name}')
        counts = {col: Counter() for col in columns}
        for values in reader:
            rows += 1
            signature = tuple(values)
            if signature in seen:
                duplicates += 1
            seen.add(signature)
            if len(values) != len(columns):
                malformed += 1
                continue
            row = dict(zip(columns, values))
            for col, value in row.items():
                counts[col][value] += 1
            for key, counter in key_counts.items():
                candidate = tuple(row[col] for col in key)
                counter[candidate] += 1
                if '' in candidate:
                    key_nulls[key] += 1
            if entity not in {'geolocation', 'reviews'}:
                retained.append(row)
    after = sha256(path)
    if before != after:
        raise RuntimeError(f'Arquivo alterado durante leitura: {path.name}')
    keys = {}
    for key, counter in key_counts.items():
        keys[' + '.join(key)] = dict(
            distinct=len(counter), rows_with_empty=key_nulls[key],
            duplicate_excess=sum(n - 1 for n in counter.values()),
            max_multiplicity=max(counter.values(), default=0),
            unique_nonnull_observed=bool(rows) and not malformed and
            not key_nulls[key] and len(counter) == rows)
    report = dict(file=path.name, bytes=path.stat().st_size, sha256=before,
                  sha256_after=after, unchanged=True, rows=rows,
                  column_count=len(columns), column_names=columns,
                  malformed_rows=malformed, exact_duplicate_excess=duplicates,
                  keys=keys, columns={col: column_profile(col, counter, rows - malformed)
                                      for col, counter in counts.items()})
    return report, retained


def relations(data):
    specs = [
        ('orders', 'customer_id', 'customers', 'customer_id'),
        ('items', 'order_id', 'orders', 'order_id'),
        ('payments', 'order_id', 'orders', 'order_id'),
        ('items', 'product_id', 'products', 'product_id'),
        ('items', 'seller_id', 'sellers', 'seller_id'),
        ('products', 'product_category_name', 'translation', 'product_category_name'),
    ]
    output = {}
    for child, ck, parent, pk in specs:
        a = Counter(r[ck] for r in data[child])
        b = Counter(r[pk] for r in data[parent])
        output[f'{child}.{ck} -> {parent}.{pk}'] = dict(
            child_empty_rows=a.get('', 0), parent_empty_rows=b.get('', 0),
            orphan_rows=sum(n for k, n in a.items() if k and k not in b),
            orphan_distinct=sum(1 for k in a if k and k not in b),
            parent_keys_without_child=sum(1 for k in b if k and k not in a),
            parent_duplicate_excess=sum(n - 1 for n in b.values()),
            children_per_present_key=distribution([n for k, n in a.items() if k]))
    return output


def commercial(data):
    orders = data['orders']
    items = Counter(r['order_id'] for r in data['items'])
    payments = Counter(r['order_id'] for r in data['payments'])
    ids = {r['order_id'] for r in orders}
    customers = defaultdict(set)
    for row in data['customers']:
        customers[row['customer_unique_id']].add(row['customer_id'])
    unique_by_id = defaultdict(set)
    for row in data['customers']:
        unique_by_id[row['customer_id']].add(row['customer_unique_id'])
    orders_by_unique = Counter()
    ambiguous_orders = 0
    for order in orders:
        matches = unique_by_id.get(order['customer_id'], set())
        if len(matches) == 1 and '' not in matches:
            orders_by_unique[next(iter(matches))] += 1
        else:
            ambiguous_orders += 1
    checks = Counter()
    pairs = [
        ('order_approved_at', 'order_purchase_timestamp'),
        ('order_delivered_carrier_date', 'order_purchase_timestamp'),
        ('order_delivered_customer_date', 'order_purchase_timestamp'),
        ('order_delivered_customer_date', 'order_delivered_carrier_date'),
    ]
    for row in orders:
        if row['order_status'] == 'delivered' and not row['order_delivered_customer_date']:
            checks['delivered_without_delivery_date'] += 1
        for end, start in pairs:
            name = f'{end}_before_{start}'
            checks.setdefault(name, 0)
            checks.setdefault(name + '_comparable', 0)
            if row[end] and row[start]:
                try:
                    a, b = datetime.fromisoformat(row[end]), datetime.fromisoformat(row[start])
                    checks[name + '_comparable'] += 1
                    checks[name] += int(a < b)
                except ValueError:
                    checks[name + '_invalid_pair'] += 1
    item_values = defaultdict(Decimal)
    pay_values = defaultdict(Decimal)
    invalid_values = Counter()
    for source, fields, target in [('items', ('price', 'freight_value'), item_values),
                                    ('payments', ('payment_value',), pay_values)]:
        for row in data[source]:
            try:
                numbers = [Decimal(row[col]) for col in fields]
                if not all(x.is_finite() for x in numbers):
                    raise ValueError('non-finite')
                target[row['order_id']] += sum(numbers)
            except (ValueError, InvalidOperation):
                invalid_values[source] += 1
    common = ids & set(item_values) & set(pay_values)
    deltas = [pay_values[k] - item_values[k] for k in sorted(common)]
    return dict(
        orders_without_items=len(ids - set(items)),
        orders_without_payments=len(ids - set(payments)),
        orders_with_multiple_items=sum(items[k] > 1 for k in ids),
        orders_with_multiple_payments=sum(payments[k] > 1 for k in ids),
        orders_with_both_multiple=sum(items[k] > 1 and payments[k] > 1 for k in ids),
        inner_join_rows_orders_items_payments=sum(items[k] * payments[k] for k in ids),
        items_on_orders_with_payments=sum(items[k] for k in ids if payments[k]),
        payments_on_orders_with_items=sum(payments[k] for k in ids if items[k]),
        items_per_order_including_zero=distribution([items[k] for k in sorted(ids)]),
        payments_per_order_including_zero=distribution([payments[k] for k in sorted(ids)]),
        customer_ids_per_unique=distribution([len(v) for v in customers.values()]),
        customer_ids_mapping_multiple_unique=sum(len(v) > 1 for v in unique_by_id.values()),
        unique_ids_with_multiple_customer_ids=sum(len(v) > 1 for v in customers.values()),
        unique_ids_with_multiple_orders=sum(v > 1 for v in orders_by_unique.values()),
        orders_per_unique=distribution(list(orders_by_unique.values())),
        orders_without_unambiguous_customer_mapping=ambiguous_orders,
        date_checks=dict(checks),
        reconciliation=dict(compared_orders=len(common), invalid_rows=dict(invalid_values),
                            payment_minus_items_and_freight=distribution([float(x) for x in deltas]),
                            absolute_difference_over_one_cent=sum(abs(x) > Decimal('0.01') for x in deltas)))


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bronze', type=Path, default=root / 'data/bronze')
    parser.add_argument('--output', type=Path, default=root / 'docs/qualidade/profiling')
    args = parser.parse_args()
    bronze, output = args.bronze.resolve(), args.output.resolve()
    if output == bronze or bronze in output.parents or output in bronze.parents:
        parser.error('Saída e Bronze devem estar em árvores separadas.')
    missing = [name for name in FILES.values() if not (bronze / name).is_file()]
    if missing:
        parser.error('Arquivos ausentes: ' + ', '.join(missing))
    output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.FileHandler(output / 'execucao.log', encoding='utf-8', mode='w'),
                                  logging.StreamHandler()])
    report = dict(started_utc=datetime.now(timezone.utc).isoformat(),
                  python=platform.python_version(), source='Arquivos locais em data/bronze; origem externa e versão não comprovadas.',
                  datasets={}, errors=[])
    try:
        data = {}
        for entity, filename in FILES.items():
            logging.info('Analisando %s', filename)
            report['datasets'][entity], data[entity] = profile(bronze / filename, entity)
            logging.info('%s: %d registros', entity, report['datasets'][entity]['rows'])
        report['relations'] = relations(data)
        # Reviews não são retidas em memória; verificar vínculos por segunda leitura.
        order_ids = {r['order_id'] for r in data['orders']}
        with (bronze / FILES['reviews']).open(encoding='utf-8-sig', newline='') as stream:
            review_orders = Counter(r['order_id'] for r in csv.DictReader(stream))
        report['reviews_orders'] = dict(
            orphan_rows=sum(n for k, n in review_orders.items() if k not in order_ids),
            orders_without_reviews=len(order_ids - set(review_orders)),
            orders_with_multiple_reviews=sum(n > 1 for n in review_orders.values()))
        report['commercial_relationships'] = commercial(data)
        for entity, filename in FILES.items():
            if sha256(bronze / filename) != report['datasets'][entity]['sha256']:
                raise RuntimeError(f'Bronze alterada: {filename}')
        logging.info('Concluído; nove hashes reconferidos; nenhuma alteração na Bronze.')
    except Exception as exc:
        report['errors'].append(f'{type(exc).__name__}: {exc}')
        logging.exception('Falha no profiling')
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (output / 'resultados.json').write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                    allow_nan=False) + '\n', encoding='utf-8')
    with (output / 'inventario.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['arquivo', 'bytes', 'registros_sem_cabecalho', 'quantidade_colunas',
                         'colunas', 'sha256_antes', 'sha256_depois'])
        for dataset in report['datasets'].values():
            writer.writerow([dataset['file'], dataset['bytes'], dataset['rows'],
                             dataset['column_count'], '|'.join(dataset['column_names']),
                             dataset['sha256'], dataset['sha256_after']])
    if report['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
