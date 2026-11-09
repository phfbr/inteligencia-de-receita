"""Silver estática via psql, sem dependências Python externas ou alteração da Bronze."""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

from profiling import DATES, FILES, KEYS, NUMERIC, sha256

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'inteligencia_receita:exclusive:v1'
MARKER = 'inteligencia_receita:silver:v1'
HEADERS = {
    'customers': 'customer_id customer_unique_id customer_zip_code_prefix customer_city customer_state',
    'geolocation': 'geolocation_zip_code_prefix geolocation_lat geolocation_lng geolocation_city geolocation_state',
    'orders': 'order_id customer_id order_status order_purchase_timestamp order_approved_at order_delivered_carrier_date order_delivered_customer_date order_estimated_delivery_date',
    'items': 'order_id order_item_id product_id seller_id shipping_limit_date price freight_value',
    'payments': 'order_id payment_sequential payment_type payment_installments payment_value',
    'reviews': 'review_id order_id review_score review_comment_title review_comment_message review_creation_date review_answer_timestamp',
    'products': 'product_id product_category_name product_name_lenght product_description_lenght product_photos_qty product_weight_g product_length_cm product_height_cm product_width_cm',
    'sellers': 'seller_id seller_zip_code_prefix seller_city seller_state',
    'translation': 'product_category_name product_category_name_english',
}
TABLES = {entity: Path(name).stem for entity, name in FILES.items()}
META = [('_source_file', 'text'), ('_source_sha256', 'text'), ('_source_row', 'bigint'),
        ('_raw_record', 'jsonb'), ('_conversion_errors', 'jsonb')]
REFS = [('orders', 'customer_id', 'customers', 'customer_id'),
        ('items', 'order_id', 'orders', 'order_id'),
        ('payments', 'order_id', 'orders', 'order_id'),
        ('reviews', 'order_id', 'orders', 'order_id'),
        ('items', 'product_id', 'products', 'product_id'),
        ('items', 'seller_id', 'sellers', 'seller_id'),
        ('products', 'product_category_name', 'translation', 'product_category_name')]


class SilverError(Exception):
    """Mensagem controlada, sem credenciais ou conteúdo de registros."""


def ident(name):
    if not re.fullmatch(r'[a-z_][a-z_0-9]*', name):
        raise SilverError('Identificador SQL fora da lista permitida.')
    return '"' + name + '"'


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def columns(entity):
    result = []
    for name in HEADERS[entity].split():
        if name in DATES:
            kind = 'timestamp without time zone'
        elif name in NUMERIC and not name.endswith('_id') and name != 'payment_sequential':
            kind = 'numeric'
        else:
            kind = 'text'
        result.append((name, kind))
    return result


def table(entity):
    return 'silver.' + ident(TABLES[entity])


def table_marker(entity):
    signature = json.dumps(columns(entity) + META, separators=(',', ':'))
    return MARKER + ':' + entity + ':' + hashlib.sha256(signature.encode()).hexdigest()


def convert(value, kind):
    if value == '':
        return None, None
    if kind == 'text':
        return value, None
    if kind == 'numeric':
        if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', value):
            return None, 'invalid_numeric'
        try:
            number = Decimal(value)
            if not number.is_finite():
                return None, 'nonfinite_numeric'
            if number.adjusted() >= 131072 or number.as_tuple().exponent < -16383:
                return None, 'numeric_out_of_range'
            return number, None
        except InvalidOperation:
            return None, 'invalid_numeric'
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?', value):
        return None, 'invalid_or_offset_timestamp'
    fraction = value.split('.', 1)[1] if '.' in value else ''
    if len(fraction) > 6:
        return None, 'unsupported_timestamp_precision'
    try:
        return datetime.fromisoformat(value), None
    except ValueError:
        return None, 'invalid_timestamp'


def copy_text(value):
    if value is None:
        return r'\N'
    if isinstance(value, datetime):
        value = value.isoformat(sep=' ')
    return str(value).replace('\\', '\\\\').replace('\t', r'\t').replace('\n', r'\n').replace('\r', r'\r')


def fingerprint_values(raw, errors, entity):
    values = [raw[name] for name, _ in columns(entity)]
    values += [errors.get(name, '') for name, _ in columns(entity)]
    return '|'.join(v.encode('utf-8').hex() for v in values).encode('ascii')


def source_scan(bronze, baseline, spool=None):
    """Compara a versão ao profiling e preserva todas as ocorrências, inclusive duplicatas."""
    results = {}
    for entity, filename in FILES.items():
        path = bronze / filename
        if not path.is_file() or sha256(path) != baseline['datasets'][entity]['sha256']:
            raise SilverError(f'Fonte ausente ou diferente do profiling: {filename}')
        stats = dict(file=filename, bytes=path.stat().st_size, sha256=sha256(path), rows=0,
                     nulls=Counter(), conversion_errors=Counter(), numeric_sums={},
                     keys={}, source_record_fingerprint=None)
        key_counts = {key: Counter() for key in KEYS[entity]}
        fingerprint = hashlib.sha256()
        sums = {name: Decimal(0) for name, kind in columns(entity) if kind == 'numeric'}
        target = (spool / (entity + '.copy')).open('w', encoding='utf-8', newline='') if spool else None
        try:
            with path.open(encoding='utf-8-sig', newline='') as stream, localcontext() as ctx:
                ctx.prec = 200000
                reader = csv.reader(stream, strict=True)
                if next(reader) != HEADERS[entity].split():
                    raise SilverError(f'Cabeçalho inesperado: {filename}')
                for row_number, values in enumerate(reader, 1):
                    if len(values) != len(columns(entity)) or any('\x00' in v for v in values):
                        raise SilverError(f'Registro não representável integralmente: {filename}, registro {row_number}')
                    raw = dict(zip(HEADERS[entity].split(), values))
                    errors, typed = {}, []
                    for (name, kind), value in zip(columns(entity), values):
                        converted, error = convert(value, kind)
                        typed.append(converted)
                        stats['nulls'][name] += int(converted is None)
                        if error:
                            errors[name] = error
                            stats['conversion_errors'][name] += 1
                        if kind == 'numeric' and converted is not None:
                            sums[name] += converted
                    for key, counter in key_counts.items():
                        counter[tuple(raw[name] for name in key)] += 1
                    fingerprint.update(hashlib.sha256(fingerprint_values(raw, errors, entity)).hexdigest().encode('ascii'))
                    if target:
                        metadata = [filename, stats['sha256'], row_number,
                                    json.dumps(raw, ensure_ascii=False), json.dumps(errors, ensure_ascii=False)]
                        target.write('\t'.join(copy_text(v) for v in typed + metadata) + '\n')
                    stats['rows'] += 1
        finally:
            if target:
                target.close()
        for key, counter in key_counts.items():
            stats['keys'][' + '.join(key)] = dict(
                distinct=len(counter), duplicate_excess=sum(n - 1 for n in counter.values()),
                rows_with_empty=sum(n for k, n in counter.items() if '' in k))
        stats['numeric_sums'] = {name: str(value) for name, value in sums.items()}
        stats['source_record_fingerprint'] = fingerprint.hexdigest()
        if stats['rows'] != baseline['datasets'][entity]['rows'] or sha256(path) != stats['sha256']:
            raise SilverError(f'Fonte alterada ou contagem diferente do profiling: {filename}')
        results[entity] = stats
    parents = {}
    for child, field, parent, pk in REFS:
        if (parent, pk) not in parents:
            with (bronze / FILES[parent]).open(encoding='utf-8-sig', newline='') as stream:
                parents[parent, pk] = {r[pk] for r in csv.DictReader(stream)}
        with (bronze / FILES[child]).open(encoding='utf-8-sig', newline='') as stream:
            orphan_rows = sum(bool(r[field]) and r[field] not in parents[parent, pk] for r in csv.DictReader(stream))
        results[child].setdefault('references', {})[field + '->' + parent + '.' + pk] = orphan_rows
    # As releituras de integridade também devem corresponder à mesma versão.
    for entity, filename in FILES.items():
        if sha256(bronze / filename) != results[entity]['sha256']:
            raise SilverError('Fonte alterada durante verificações de integridade.')
    return results


def guard_sql():
    """Validação antes de DDL/DELETE; não adota schemas ou tabelas de terceiros."""
    allowed = []
    for name in TABLES.values():
        allowed.extend([name, name + '_pkey'])
    permitted = ','.join(literal(name) for name in allowed)
    sql = f"""DO $guard$
BEGIN
 IF current_database() IS DISTINCT FROM current_setting('olist.expected_database', true)
    OR current_setting('server_encoding') <> 'UTF8'
    OR current_setting('server_version_num')::integer < 140000 THEN
   RAISE EXCEPTION 'Destino ou servidor incompatível';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_database d WHERE d.datname=current_database()
     AND pg_get_userbyid(d.datdba)=current_user
     AND shobj_description(d.oid,'pg_database')={literal(PROJECT)}) THEN
   RAISE EXCEPTION 'Exclusividade do projeto não comprovada';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname !~ '^pg_'
     AND nspname NOT IN ('information_schema','public','silver'))
 OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
       AND NOT (n.nspname='silver' AND c.relname IN ({permitted}) AND c.relkind IN ('r','i')))
 OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema')
 OR EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
     WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
       AND t.typrelid=0 AND t.typelem=0)
 OR EXISTS (SELECT 1 FROM pg_extension WHERE extname <> 'plpgsql')
 OR EXISTS (SELECT 1 FROM pg_event_trigger) THEN
   RAISE EXCEPTION 'Objetos externos encontrados; operação recusada';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='silver' AND
     (obj_description(oid,'pg_namespace') IS DISTINCT FROM {literal(MARKER)}
       OR pg_get_userbyid(nspowner) <> current_user)) THEN
   RAISE EXCEPTION 'Schema silver sem identificação exclusiva do projeto';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
      JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='silver' AND NOT t.tgisinternal)
 OR EXISTS (SELECT 1 FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid
      JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='silver')
 OR EXISTS (SELECT 1 FROM pg_rewrite r JOIN pg_class c ON c.oid=r.ev_class
      JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='silver') THEN
   RAISE EXCEPTION 'Triggers ou regras não previstos';
 END IF;
"""
    for entity, name in TABLES.items():
        expected = [dict(name=n, type=t, required=False) for n, t in columns(entity)]
        expected += [dict(name=n, type=t, required=True) for n, t in META]
        sql += f"""
 IF to_regclass({literal('silver.' + name)}) IS NOT NULL THEN
   IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass({literal('silver.' + name)})
       AND c.relkind='r' AND NOT c.relispartition AND NOT c.relrowsecurity
       AND pg_get_userbyid(c.relowner)=current_user
       AND obj_description(c.oid,'pg_class')={literal(table_marker(entity))})
   OR (SELECT jsonb_agg(jsonb_build_object('name',a.attname,'type',format_type(a.atttypid,a.atttypmod),
               'required',a.attnotnull) ORDER BY a.attnum) FROM pg_attribute a
         WHERE a.attrelid=to_regclass({literal('silver.' + name)}) AND a.attnum>0 AND NOT a.attisdropped)
       IS DISTINCT FROM {literal(json.dumps(expected))}::jsonb
   OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass({literal('silver.' + name)}))
   OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=to_regclass({literal('silver.' + name)})
       AND a.attnum>0 AND NOT a.attisdropped AND a.atttypid='text'::regtype
       AND a.attname NOT LIKE '\\_%' ESCAPE '\\' AND a.attcollation <> '"C"'::regcollation)
   OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass({literal('silver.' + name)}) AND contype <> 'n') <> 1
   OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass({literal('silver.' + name)})
       AND contype='p' AND pg_get_constraintdef(oid)='PRIMARY KEY (_source_row)') THEN
     RAISE EXCEPTION 'Tabela existente incompatível: {name}';
   END IF;
 END IF;
"""
    return sql + 'END $guard$;\n'


def ddl_sql():
    statements = ['-- Executar somente pelo orquestrador silver.py: ele verifica o destino e abre a transação.\n',
                  guard_sql(), 'CREATE SCHEMA IF NOT EXISTS silver;\n',
                  f'COMMENT ON SCHEMA silver IS {literal(MARKER)};\n']
    for entity in TABLES:
        defs = [ident(n) + ' ' + t + (' COLLATE "C"' if t == 'text' else '') for n, t in columns(entity)]
        defs += [ident(n) + ' ' + t + ' NOT NULL' + (' PRIMARY KEY' if n == '_source_row' else '') for n, t in META]
        statements += [f'CREATE TABLE IF NOT EXISTS {table(entity)} (\n  ' + ',\n  '.join(defs) + '\n);\n',
                       f'COMMENT ON TABLE {table(entity)} IS {literal(table_marker(entity))};\n']
    return ''.join(statements)


def row_fingerprint_sql(entity):
    parts = [f"encode(convert_to(_raw_record->>{literal(name)},'UTF8'),'hex')" for name, _ in columns(entity)]
    parts += [f"encode(convert_to(COALESCE(_conversion_errors->>{literal(name)},''),'UTF8'),'hex')"
              for name, _ in columns(entity)]
    row = "encode(sha256(convert_to(concat_ws('|'," + ','.join(parts) + "),'UTF8')),'hex')"
    return "encode(sha256(convert_to(COALESCE(string_agg(" + row + ",'' ORDER BY _source_row),''),'UTF8')),'hex')"


def observation_sql():
    statements = ['-- Consultas de qualidade; nenhuma transformação ou exclusão.\n']
    for entity in TABLES:
        statements.append(f"SELECT json_build_object('table',{literal(TABLES[entity])},'rows',count(*),"
                          f"'conversion_error_rows',count(*) FILTER (WHERE _conversion_errors <> '{{}}'::jsonb)) FROM {table(entity)};\n")
    for child, field, parent, pk in REFS:
        statements.append(f"SELECT json_build_object('reference',{literal(child+'.'+field+'->'+parent+'.'+pk)},"
                          f"'orphans',count(*)) FROM {table(child)} c WHERE c.{ident(field)} IS NOT NULL AND NOT EXISTS "
                          f"(SELECT 1 FROM {table(parent)} p WHERE p.{ident(pk)}=c.{ident(field)});\n")
    statements.append("""WITH i AS (SELECT order_id,sum(price) price,sum(freight_value) freight
 FROM silver.olist_order_items_dataset GROUP BY order_id),
 p AS (SELECT order_id,sum(payment_value) payment FROM silver.olist_order_payments_dataset GROUP BY order_id)
SELECT json_build_object('reconciliation_compared',count(*),'over_one_cent',count(*) FILTER
 (WHERE abs(p.payment-i.price-i.freight)>0.01),'positive',count(*) FILTER
 (WHERE p.payment-i.price-i.freight>0.01),'negative',count(*) FILTER
 (WHERE p.payment-i.price-i.freight < -0.01))
FROM silver.olist_orders_dataset o JOIN i USING(order_id) JOIN p USING(order_id);
""")
    return ''.join(statements)


def validation_sql(stats):
    checks = []
    for entity, st in stats.items():
        t = table(entity)
        conditions = [f'count(*) <> {st["rows"]}', f'COALESCE(min(_source_row),0) <> {1 if st["rows"] else 0}',
                      f'COALESCE(max(_source_row),0) <> {st["rows"]}',
                      f'count(*) FILTER (WHERE _source_file IS DISTINCT FROM {literal(st["file"])} OR '
                      f'_source_sha256 IS DISTINCT FROM {literal(st["sha256"])}) <> 0',
                      f'{row_fingerprint_sql(entity)} IS DISTINCT FROM {literal(st["source_record_fingerprint"])}']
        domain = 'ARRAY[' + ','.join(literal(n) for n, _ in columns(entity)) + ']::text[]'
        conditions += ["count(*) FILTER (WHERE jsonb_typeof(_raw_record) IS DISTINCT FROM 'object' "
                       f"OR _raw_record - {domain} <> '{{}}'::jsonb) <> 0",
                       "count(*) FILTER (WHERE jsonb_typeof(_conversion_errors) IS DISTINCT FROM 'object' "
                       f"OR _conversion_errors - {domain} <> '{{}}'::jsonb) <> 0"]
        for name, kind in columns(entity):
            col = ident(name)
            conditions.append(f'count(*) FILTER (WHERE {col} IS NULL) <> {st["nulls"][name]}')
            conditions.append(f'count(*) FILTER (WHERE _conversion_errors ? {literal(name)}) <> {st["conversion_errors"].get(name,0)}')
            expected = f"NULLIF(_raw_record->>{literal(name)},'')"
            if kind != 'text':
                expected = f'CASE WHEN _conversion_errors ? {literal(name)} THEN NULL ELSE ({expected})::{kind} END'
            conditions.append(f'count(*) FILTER (WHERE {col} IS DISTINCT FROM ({expected})) <> 0')
            if kind == 'numeric':
                conditions.append(f'COALESCE(sum({col}),0) IS DISTINCT FROM {literal(st["numeric_sums"][name])}::numeric')
        for fields in KEYS[entity]:
            k = st['keys'][' + '.join(fields)]
            group = ','.join(ident(n) for n in fields)
            checks.append(f"IF (SELECT count(*) FROM (SELECT {group} FROM {t} GROUP BY {group}) k) <> {k['distinct']} THEN "
                          f"RAISE EXCEPTION 'Cardinalidade da chave difere da Bronze: {TABLES[entity]}'; END IF;")
        checks.append(f"IF (SELECT {' OR '.join(conditions)} FROM {t}) THEN RAISE EXCEPTION 'Bronze-Silver difere: {TABLES[entity]}'; END IF;")
    for child, field, parent, pk in REFS:
        expected = stats[child]['references'][field + '->' + parent + '.' + pk]
        checks.append(f"IF (SELECT count(*) FROM {table(child)} c WHERE c.{ident(field)} IS NOT NULL "
                      f"AND NOT EXISTS (SELECT 1 FROM {table(parent)} p WHERE p.{ident(pk)}=c.{ident(field)})) <> {expected} THEN "
                      f"RAISE EXCEPTION 'Integridade difere da Bronze: {child}.{field}'; END IF;")
    return 'DO $validation$ BEGIN\n' + '\n'.join(checks) + '\nEND $validation$;\n'


def psql_path():
    explicit = os.environ.get('OLIST_PSQL')
    if explicit:
        return explicit if Path(explicit).is_file() else None
    found = shutil.which('psql')
    if found:
        return found
    root = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'PostgreSQL'
    installed = sorted(root.glob('*/bin/psql.exe'), reverse=True) if root.is_dir() else []
    return str(installed[0]) if installed else None


def environment_status():
    names = ('PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'OLIST_PROJECT_DATABASE')
    present = {name: bool(os.environ.get(name)) for name in names}
    credential = bool(os.environ.get('PGPASSWORD')) or bool(os.environ.get('PGPASSFILE') and Path(os.environ['PGPASSFILE']).is_file())
    missing = [name for name, configured in present.items() if not configured]
    if not credential:
        missing.append('PGPASSWORD ou PGPASSFILE explícito')
    if not psql_path():
        missing.append('psql')
    if present['PGDATABASE'] and present['OLIST_PROJECT_DATABASE'] and os.environ['PGDATABASE'] != os.environ['OLIST_PROJECT_DATABASE']:
        missing.append('PGDATABASE deve coincidir com OLIST_PROJECT_DATABASE')
    return dict(configured=present, explicit_credential_present=credential,
                psql_available=bool(psql_path()), blockers=missing)


def run_psql(sql_file):
    env = os.environ.copy()
    env.update(PGCONNECT_TIMEOUT='5', PGCLIENTENCODING='UTF8', PSQLRC=os.devnull)
    # Não imprimir argv com URI, ambiente, stderr do servidor ou valores de registros.
    try:
        result = subprocess.run([psql_path(), '-X', '-w', '-q', '-A', '-t',
                                 '--set=ON_ERROR_STOP=1', '--set=VERBOSITY=sqlstate',
                                 '--file', str(sql_file)], env=env, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=1800)
    except (OSError, subprocess.TimeoutExpired):
        raise SilverError('psql indisponível ou tempo de execução excedido; verificar estado do banco antes de repetir.') from None
    if result.returncode:
        # O prefixo do servidor pode ser localizado (por exemplo, ERRO em pt-BR).
        states = re.findall(r':\s+([0-9A-Z]{5})(?=\s|$)', result.stderr)
        raise SilverError(f'psql falhou (código {result.returncode}, SQLSTATE {states[-1] if states else "não disponível"}); detalhes privados não registrados.')
    return [json.loads(line) for line in result.stdout.splitlines() if line.lstrip().startswith('{')]


def transaction_prefix(readonly=False):
    expected = os.environ.get('OLIST_PROJECT_DATABASE', '')
    return ("\\set ON_ERROR_STOP on\nBEGIN" + (' READ ONLY' if readonly else '') + ";\n"
            "SET LOCAL search_path=pg_catalog;\nSET LOCAL datestyle='ISO, YMD';\n"
            "SET LOCAL standard_conforming_strings=on;\nSET LOCAL statement_timeout='15min';\n"
            "SET LOCAL lock_timeout='5s';\n" +
            f"SELECT set_config('olist.expected_database',{literal(expected)},true) IS NOT NULL;\n")


def preflight(work):
    path = work / 'preflight.sql'
    path.write_text(transaction_prefix(True) + guard_sql() +
                    "SELECT json_build_object('connection','verified','project_exclusive',true," 
                    "'server_version',current_setting('server_version'));\nROLLBACK;\n", encoding='utf-8')
    return run_psql(path)


def write_load(path, stats, spool, inject_failure=False):
    if (ROOT / 'sql/silver/001_estrutura.sql').read_text(encoding='utf-8') != ddl_sql() or (
            ROOT / 'sql/validacoes/silver.sql').read_text(encoding='utf-8') != observation_sql():
        raise SilverError('SQL difere da especificação revisada; revisar código e testes antes de executar.')
    with path.open('w', encoding='utf-8', newline='') as stream:
        stream.write(transaction_prefix() + "SELECT pg_advisory_xact_lock(871204031);\n")
        stream.write((ROOT / 'sql/silver/001_estrutura.sql').read_text(encoding='utf-8'))
        for entity in TABLES:
            # Só tabelas marcadas do projeto; sem TRUNCATE, DROP, CASCADE ou filtros de negócio.
            stream.write(f'DELETE FROM {table(entity)};\n')
            names = ','.join(ident(n) for n, _ in columns(entity) + META)
            stream.write(f'COPY {table(entity)} ({names}) FROM STDIN;\n')
            with (spool / (entity + '.copy')).open(encoding='utf-8', newline='') as data:
                shutil.copyfileobj(data, stream)
            stream.write('\\.\n')
        stream.write(guard_sql())
        stream.write(validation_sql(stats))
        stream.write((ROOT / 'sql/validacoes/silver.sql').read_text(encoding='utf-8'))
        if inject_failure:
            stream.write('SELECT 1/0; -- teste explícito de rollback\n')
        stream.write('COMMIT;\n')


def execute(mode, bronze, baseline_path, output, inject_failure=False):
    if (output / 'resultado.json').exists():
        raise SilverError('Saída já contém resultado; use diretório novo para preservar evidências.')
    if output == bronze or bronze in output.parents or output in bronze.parents:
        raise SilverError('Saída e Bronze devem estar em árvores separadas.')
    output.mkdir(parents=True, exist_ok=True)
    report = dict(mode=mode, started_utc=datetime.now(timezone.utc).isoformat(),
                  database_load_completed=False, environment=environment_status(), sources={},
                  database_results=[], errors=[], status='started')
    log = ['Início: ' + report['started_utc'], 'Modo: ' + mode]
    try:
        baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='olist_silver_') as temp:
            work = Path(temp)
            report['sources'] = source_scan(bronze, baseline, work if mode == 'load' else None)
            log.append('Nove fontes comparadas ao profiling; contagens, originais, tipos e hashes examinados.')
            if report['environment']['blockers']:
                report['status'] = 'blocked'
                log.append('Bloqueio: ' + '; '.join(report['environment']['blockers']))
            else:
                report['preflight'] = preflight(work)
                log.append('Conexão e exclusividade verificadas por leitura antes de qualquer escrita.')
                if mode == 'load':
                    script = work / 'load.sql'
                    write_load(script, report['sources'], work, inject_failure)
                    # Detecta mudanças nas fontes antes de enviar comandos de escrita.
                    for entity, filename in FILES.items():
                        if sha256(bronze / filename) != report['sources'][entity]['sha256']:
                            raise SilverError('Bronze alterada durante preparação; nenhuma carga enviada.')
                    report['database_results'] = run_psql(script)
                    report['database_load_completed'] = True
                    report['status'] = 'committed'
                    log.append('COMMIT confirmado pelo processo psql; testes Bronze-Silver executados na mesma transação.')
                elif mode == 'verify':
                    script = work / 'verify.sql'
                    script.write_text(transaction_prefix(True) + guard_sql() + validation_sql(report['sources']) +
                                      observation_sql() + 'ROLLBACK;\n', encoding='utf-8')
                    report['database_results'] = run_psql(script)
                    report['status'] = 'verified_readonly'
                else:
                    report['status'] = 'prepared_connection_verified'
            report['sources_unchanged_after'] = all(
                sha256(bronze / filename) == report['sources'][entity]['sha256'] for entity, filename in FILES.items())
            if not report['sources_unchanged_after']:
                raise SilverError('Fonte alterada por processo externo; verificar estado do banco e manifestos.')
    except Exception as exc:
        report['status'] = 'failed'
        report['errors'].append(str(exc) if isinstance(exc, SilverError) else type(exc).__name__)
        log.append('Falha controlada: ' + report['errors'][-1])
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    (output / 'resultado.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (output / 'execucao.log').write_text('\n'.join(log) + '\nEstado: ' + report['status'] + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('prepare', 'load', 'verify'), default='prepare')
    parser.add_argument('--bronze', type=Path, default=ROOT / 'data/bronze')
    parser.add_argument('--baseline', type=Path, default=ROOT / 'docs/qualidade/profiling/resultados.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/qualidade/etapa4_silver')
    args = parser.parse_args()
    try:
        report = execute(args.mode, args.bronze.resolve(), args.baseline.resolve(), args.output.resolve())
    except SilverError as exc:
        parser.error(str(exc))
    print(json.dumps(dict(status=report['status'], database_load_completed=report['database_load_completed'],
                         source_rows={k: v['rows'] for k, v in report['sources'].items()},
                         blockers=report['environment']['blockers'], errors=report['errors']), ensure_ascii=True))
    raise SystemExit(2 if report['status'] == 'blocked' else 1 if report['errors'] else 0)


if __name__ == '__main__':
    main()
