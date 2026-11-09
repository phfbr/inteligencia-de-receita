"""Diagnósticos da Etapa 3, somente leitura. Python >= 3.10; biblioteca padrão."""
import argparse
import csv
import json
import logging
import platform
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from profiling import FILES, KEYS, sha256

ENTITIES = ('orders', 'items', 'payments', 'customers')
DATE_FIELDS = ('order_purchase_timestamp', 'order_approved_at',
               'order_delivered_carrier_date', 'order_delivered_customer_date',
               'order_estimated_delivery_date')


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f'Cabeçalho inválido: {path.name}')
        rows = []
        for row in reader:
            if None in row or None in row.values():
                raise ValueError(f'Registro com largura incorreta: {path.name}')
            rows.append(row)
        return rows


def magnitude(delta):
    value = abs(delta)
    if value <= Decimal('0.01'):
        return '<=0.01'
    for upper in ('0.10', '1', '10', '50', '100'):
        if value <= Decimal(upper):
            return {'0.10': '(0.01,0.10]', '1': '(0.10,1]', '10': '(1,10]',
                    '50': '(10,50]', '100': '(50,100]'}[upper]
    return '>100'


def key_profile(rows, fields):
    counts = Counter(tuple(row[field] for field in fields) for row in rows)
    return dict(rows=len(rows), distinct=len(counts),
                empty_rows=sum(n for key, n in counts.items() if '' in key),
                duplicate_excess=sum(n - 1 for n in counts.values()),
                duplicate_groups=sum(n > 1 for n in counts.values()),
                max_multiplicity=max(counts.values(), default=0))


def analyze(data):
    report = {}
    report['keys'] = {entity: {' + '.join(fields): key_profile(data[entity], fields)
                              for fields in KEYS[entity]} for entity in ENTITIES}
    # Agregações no grão do pedido exigem chaves únicas e preenchidas.
    for entity, fields in [('orders', ('order_id',)), ('items', ('order_id', 'order_item_id')),
                           ('payments', ('order_id', 'payment_sequential')),
                           ('customers', ('customer_id',))]:
        key = report['keys'][entity][' + '.join(fields)]
        if key['empty_rows'] or key['duplicate_excess']:
            raise ValueError(f'Chave ambígua em {entity}: {fields}; nenhuma deduplicação aplicada')
    order_ids = {row['order_id'] for row in data['orders']}
    customer_map = {row['customer_id']: row['customer_unique_id'] for row in data['customers']}
    refs = {}
    for child, field, parents in [('items', 'order_id', order_ids),
                                   ('payments', 'order_id', order_ids),
                                   ('orders', 'customer_id', set(customer_map))]:
        counts = Counter(row[field] for row in data[child])
        refs[f'{child}.{field}'] = dict(empty_rows=counts.get('', 0),
                                       orphan_rows=sum(n for k, n in counts.items() if k and k not in parents),
                                       orphan_distinct=sum(bool(k) and k not in parents for k in counts))
    report['references'] = refs
    item_counts, payment_counts = Counter(), Counter()
    item_totals, payment_totals = defaultdict(Decimal), defaultdict(Decimal)
    for entity, fields, counts, totals in [
        ('items', ('price', 'freight_value'), item_counts, item_totals),
        ('payments', ('payment_value',), payment_counts, payment_totals),
    ]:
        for row in data[entity]:
            values = [Decimal(row[field]) for field in fields]
            if not all(value.is_finite() for value in values):
                raise ValueError(f'Valor não finito em {entity}')
            counts[row['order_id']] += 1
            totals[row['order_id']] += sum(values, Decimal(0))

    status = {}
    missing = []
    divergent = []
    cross = Counter()
    reconciliation = Counter()
    deltas = []
    groups = defaultdict(list)
    unmapped = []
    for row in data['orders']:
        oid, state = row['order_id'], row['order_status']
        has_items, has_payments = bool(item_counts[oid]), bool(payment_counts[oid])
        # Falha explícita em data inválida; não se descarta registro silenciosamente.
        dates = {field: datetime.fromisoformat(row[field]) if row[field] else None
                 for field in DATE_FIELDS}
        if state not in status:
            status[state] = dict(orders=0, with_items=0, without_items=0,
                                 with_payments=0, without_payments=0,
                                 with_both=0, without_both=0,
                                 **{field + '_present': 0 for field in DATE_FIELDS},
                                 both_actual_delivery_dates=0,
                                 actual_customer_delivery_without_items=0,
                                 actual_customer_delivery_without_payments=0)
        s = status[state]
        s['orders'] += 1
        s['with_items' if has_items else 'without_items'] += 1
        s['with_payments' if has_payments else 'without_payments'] += 1
        s['with_both'] += int(has_items and has_payments)
        s['without_both'] += int(not has_items and not has_payments)
        for field in DATE_FIELDS:
            s[field + '_present'] += int(dates[field] is not None)
        s['both_actual_delivery_dates'] += int(bool(dates['order_delivered_carrier_date'] and
                                                   dates['order_delivered_customer_date']))
        s['actual_customer_delivery_without_items'] += int(bool(dates['order_delivered_customer_date']) and not has_items)
        s['actual_customer_delivery_without_payments'] += int(bool(dates['order_delivered_customer_date']) and not has_payments)
        if not has_items or not has_payments:
            missing.append(dict(order_id=oid, status=state, item_rows=item_counts[oid],
                                payment_rows=payment_counts[oid],
                                **{field: row[field] for field in DATE_FIELDS}))
        if has_items and has_payments:
            delta = payment_totals[oid] - item_totals[oid]
            deltas.append(delta)
            reconciliation['compared'] += 1
            reconciliation['exact_zero'] += int(delta == 0)
            reconciliation['nonzero_at_most_one_cent'] += int(0 < abs(delta) <= Decimal('0.01'))
            if abs(delta) > Decimal('0.01'):
                sign = 'positive' if delta > 0 else 'negative'
                band = magnitude(delta)
                cross[(state, band, sign)] += 1
                divergent.append(dict(order_id=oid, status=state, item_rows=item_counts[oid],
                                      payment_rows=payment_counts[oid],
                                      items_plus_freight=item_totals[oid], payments=payment_totals[oid],
                                      delta=delta, sign=sign, magnitude=band))
        uid = customer_map.get(row['customer_id'])
        if uid:
            groups[uid].append(row)
        else:
            unmapped.append(oid)
    report['status'] = dict(sorted(status.items()))
    report['missing'] = dict(without_items=sum(s['without_items'] for s in status.values()),
                             without_payments=sum(s['without_payments'] for s in status.values()),
                             without_either=len(missing))
    report['reconciliation'] = dict(reconciliation,
        divergent=len(divergent), positive=sum(row['delta'] > 0 for row in divergent),
        negative=sum(row['delta'] < 0 for row in divergent),
        min_delta=min((r['delta'] for r in divergent), default=None),
        max_delta=max((r['delta'] for r in divergent), default=None),
        diagnostic_delta_sum=sum((r['delta'] for r in divergent), Decimal(0)),
        cross=[dict(status=s, magnitude=b, sign=g, orders=n)
               for (s, b, g), n in sorted(cross.items())])
    clients = []
    sequence = []
    adjacent = []
    transitions = Counter()
    timing = Counter()
    multi_status = defaultdict(Counter)
    signature_counts = Counter()
    for uid, rows in sorted(groups.items()):
        if len(rows) < 2:
            continue
        ordered = sorted(rows, key=lambda r: (r['order_purchase_timestamp'], r['order_id']))
        states = Counter(r['order_status'] for r in rows)
        signature_counts[tuple(sorted(states))] += 1
        for state, count in states.items():
            multi_status[state]['customers_with_status'] += 1
            multi_status[state]['orders'] += count
            multi_status[state]['customers_with_at_least_two_of_status'] += int(count >= 2)
        stamps = [datetime.fromisoformat(r['order_purchase_timestamp'])
                  if r['order_purchase_timestamp'] else None for r in ordered]
        valid = [stamp for stamp in stamps if stamp is not None]
        timestamp_counts = Counter(valid)
        same_time = any(n > 1 for n in timestamp_counts.values())
        day_counts = Counter(t.date() for t in valid)
        same_day = any(n > 1 for n in day_counts.values())
        gaps = []
        for index, row in enumerate(ordered):
            sequence.append(dict(customer_unique_id=uid, position=index + 1,
                                 order_id=row['order_id'], customer_id=row['customer_id'],
                                 status=row['order_status'], purchase=row['order_purchase_timestamp'],
                                 delivery=row['order_delivered_customer_date']))
            if not index or stamps[index] is None or stamps[index - 1] is None:
                continue
            seconds = int((stamps[index] - stamps[index - 1]).total_seconds())
            gaps.append(seconds)
            a, b = ordered[index - 1]['order_status'], row['order_status']
            transitions[(a, b, 'equal_timestamp' if seconds == 0 else 'later_timestamp')] += 1
            timing['adjacent_pairs'] += 1
            for name, condition in [('equal_timestamp', seconds == 0),
                                    ('positive_at_most_60s', 0 < seconds <= 60),
                                    ('positive_at_most_1h', 0 < seconds <= 3600),
                                    ('positive_at_most_24h', 0 < seconds <= 86400)]:
                timing[name] += int(condition)
            adjacent.append(dict(customer_unique_id=uid, earlier_order_id=ordered[index - 1]['order_id'],
                                 later_order_id=row['order_id'], earlier_status=a, later_status=b,
                                 earlier_purchase=ordered[index - 1]['order_purchase_timestamp'],
                                 later_purchase=row['order_purchase_timestamp'], gap_seconds=seconds))
        clients.append(dict(customer_unique_id=uid, orders=len(rows),
                            statuses=json.dumps(dict(sorted(states.items())), sort_keys=True),
                            first_purchase=min(valid).isoformat() if valid else '',
                            last_purchase=max(valid).isoformat() if valid else '',
                            missing_purchase_dates=len(rows) - len(valid),
                            same_timestamp=same_time, same_calendar_day=same_day,
                            equal_timestamp_pairs=sum(n * (n - 1) // 2 for n in timestamp_counts.values()),
                            distinct_calendar_days=len(day_counts),
                            min_adjacent_gap_seconds=min(gaps) if gaps else '',
                            positive_gap_at_most_60s=any(0 < n <= 60 for n in gaps),
                            positive_gap_at_most_1h=any(0 < n <= 3600 for n in gaps),
                            positive_gap_at_most_24h=any(0 < n <= 86400 for n in gaps)))
    report['customers'] = dict(
        mapped_unique_ids=len(groups), unmapped_orders=unmapped,
        multiple_order_customers=len(clients), orders_in_multiple_groups=len(sequence),
        status=dict(sorted(multi_status.items())),
        status_combinations=[dict(statuses=list(states), customers=n)
                             for states, n in sorted(signature_counts.items())],
        all_delivered=sum(json.loads(c['statuses']).get('delivered', 0) == c['orders'] for c in clients),
        at_least_two_delivered=sum(json.loads(c['statuses']).get('delivered', 0) >= 2 for c in clients),
        with_any_nondelivered=sum(any(s != 'delivered' for s in json.loads(c['statuses'])) for c in clients),
        same_timestamp_customers=sum(c['same_timestamp'] for c in clients),
        equal_timestamp_unordered_pairs=sum(c['equal_timestamp_pairs'] for c in clients),
        same_calendar_day_customers=sum(c['same_calendar_day'] for c in clients),
        multiple_calendar_days_customers=sum(c['distinct_calendar_days'] > 1 for c in clients),
        customers_with_missing_purchase_dates=sum(c['missing_purchase_dates'] > 0 for c in clients),
        positive_gap_at_most_60s_customers=sum(c['positive_gap_at_most_60s'] for c in clients),
        positive_gap_at_most_1h_customers=sum(c['positive_gap_at_most_1h'] for c in clients),
        positive_gap_at_most_24h_customers=sum(c['positive_gap_at_most_24h'] for c in clients),
        adjacent_timing=dict(timing),
        transitions=[dict(earlier_status=a, later_status=b, chronology=c, pairs=n)
                     for (a, b, c), n in sorted(transitions.items())])
    details = dict(pedidos_sem_itens_ou_pagamentos=missing, divergencias=divergent,
                   clientes_multiplos=clients, sequencia_pedidos=sequence, pares_consecutivos=adjacent)
    return report, details


def write_csv(path, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bronze', type=Path, default=root / 'data/bronze')
    parser.add_argument('--profiling', type=Path, default=root / 'docs/qualidade/profiling/resultados.json')
    parser.add_argument('--output', type=Path, default=root / 'docs/regras_negocio/evidencias')
    args = parser.parse_args()
    bronze, output = args.bronze.resolve(), args.output.resolve()
    if output == bronze or bronze in output.parents or output in bronze.parents:
        parser.error('Saída e Bronze devem estar em árvores separadas.')
    if (output / 'diagnostico.json').exists():
        parser.error('Saída já contém diagnóstico. Use outro --output para preservar evidências.')
    baseline = json.loads(args.profiling.read_text(encoding='utf-8'))
    before = {entity: sha256(bronze / name) for entity, name in FILES.items()}
    for entity, digest in before.items():
        if digest != baseline['datasets'][entity]['sha256']:
            parser.error(f'Hash diferente do profiling: {entity}')
    output.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.FileHandler(output / 'execucao.log', encoding='utf-8'),
                                  logging.StreamHandler()])
    started = datetime.now(timezone.utc).isoformat()
    try:
        data = {entity: read_csv(bronze / FILES[entity]) for entity in ENTITIES}
        for entity, rows in data.items():
            if len(rows) != baseline['datasets'][entity]['rows']:
                raise ValueError(f'Contagem difere do profiling: {entity}')
            logging.info('%s: %d registros', entity, len(rows))
        report, details = analyze(data)
        expected = baseline['commercial_relationships']
        assert report['missing']['without_items'] == expected['orders_without_items']
        assert report['missing']['without_payments'] == expected['orders_without_payments']
        assert report['reconciliation']['divergent'] == expected['reconciliation']['absolute_difference_over_one_cent']
        assert report['customers']['multiple_order_customers'] == expected['unique_ids_with_multiple_orders']
        after = {entity: sha256(bronze / name) for entity, name in FILES.items()}
        if before != after:
            raise RuntimeError('Bronze alterada durante análise')
        report['execution'] = dict(started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
                                   python=platform.python_version(), source_sha256_before=before,
                                   source_sha256_after=after, profiling_sha256=sha256(args.profiling),
                                   script_sha256=sha256(Path(__file__)), errors=[])
        (output / 'diagnostico.json').write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                          default=str, allow_nan=False) + '\n', encoding='utf-8')
        for name, rows in details.items():
            write_csv(output / (name + '.csv'), rows)
        logging.info('Ausências, divergências e grupos múltiplos reconciliados com o profiling.')
        logging.info('Concluído sem erros. Nove hashes iguais antes/depois e ao profiling existente.')
    except Exception:
        logging.exception('Falha; nenhuma fonte foi corrigida ou excluída.')
        raise


if __name__ == '__main__':
    main()
