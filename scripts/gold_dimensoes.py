"""Etapa 4B: seis dimensões estáticas; leitura da Silver, escrita somente na Gold."""
import argparse
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import silver as s

MARKER = 'inteligencia_receita:gold_dimensoes:v1'
EVIDENCE = s.ROOT / 'docs/qualidade/etapa4_silver/conclusao_20261108T024814481530Z'
SPECS = {
    'dim_clientes': ('cliente_sk', [('customer_unique_id', 'text')], [],
        'SELECT DISTINCT customer_unique_id FROM silver.olist_customers_dataset WHERE customer_unique_id IS NOT NULL'),
    'dim_produtos': ('produto_sk', [('product_id', 'text')],
        [(n, t) for n, t in s.columns('products') if n != 'product_id'] + [('product_category_name_english', 'text')],
        'SELECT p.*,t.product_category_name_english FROM silver.olist_products_dataset p '
        'LEFT JOIN silver.product_category_name_translation t ON t.product_category_name=p.product_category_name '
        'WHERE p.product_id IS NOT NULL'),
    'dim_vendedores': ('vendedor_sk', [('seller_id', 'text')],
        [(n, t) for n, t in s.columns('sellers') if n != 'seller_id'],
        'SELECT * FROM silver.olist_sellers_dataset WHERE seller_id IS NOT NULL'),
    'dim_calendario': ('data_sk', [('dia', 'date')],
        [('ano', 'integer'), ('mes', 'integer'), ('dia_mes', 'integer')], ''),
    'dim_localizacao': ('localizacao_sk', [('customer_zip_code_prefix', 'text'), ('customer_city', 'text'), ('customer_state', 'text')], [],
        'SELECT DISTINCT c.customer_zip_code_prefix,c.customer_city,c.customer_state '
        'FROM silver.olist_orders_dataset o JOIN silver.olist_customers_dataset c ON c.customer_id=o.customer_id '
        'WHERE c.customer_zip_code_prefix IS NOT NULL AND c.customer_city IS NOT NULL AND c.customer_state IS NOT NULL'),
    'dim_forma_pagamento': ('forma_pagamento_sk', [('payment_type', 'text')], [],
        'SELECT DISTINCT payment_type FROM silver.olist_order_payments_dataset WHERE payment_type IS NOT NULL'),
}
ROLES = [('orders', field) for field in (
    'order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_date',
    'order_delivered_customer_date', 'order_estimated_delivery_date')]
ROLES += [('items', 'shipping_limit_date')]


def tbl(name):
    return 'gold.' + s.ident(name)


def fields(name):
    sk, nk, attrs, _ = SPECS[name]
    return [(sk, 'bigint')] + nk + attrs + [('membro_tipo', 'text')]


def calendar_days():
    return ' UNION ALL '.join(f'SELECT {s.ident(field)}::date AS dia FROM {s.table(entity)} '
                              f'WHERE {s.ident(field)} IS NOT NULL' for entity, field in ROLES)


def source(name):
    if name == 'dim_calendario':
        return ("WITH limites AS (SELECT min(dia) inicio,max(dia) fim FROM (" + calendar_days() +
                ") d), dias AS (SELECT inicio+g AS dia FROM limites "
                "CROSS JOIN LATERAL generate_series(0,fim-inicio) g) "
                "SELECT dia,extract(year FROM dia)::integer ano,extract(month FROM dia)::integer mes,"
                "extract(day FROM dia)::integer dia_mes FROM dias")
    _, nk, attrs, query = SPECS[name]
    cols = ','.join(s.ident(n) for n, _ in nk + attrs)
    return f'SELECT {cols} FROM ({query}) origem'


def expected(name):
    sk, nk, attrs, _ = SPECS[name]
    order = ','.join(s.ident(n) + (' COLLATE "C"' if t == 'text' else '') for n, t in nk)
    cols = ','.join(s.ident(n) for n, _ in nk + attrs)
    normal = f"SELECT row_number() OVER (ORDER BY {order})::bigint {s.ident(sk)},{cols},'regular'::text membro_tipo FROM ({source(name)}) src"
    nulls = ','.join('NULL::' + t for _, t in nk + attrs)
    return normal + f" UNION ALL SELECT -1::bigint,{nulls},'nao_informado'::text" + \
        f" UNION ALL SELECT -2::bigint,{nulls},'referencia_nao_encontrada'::text"


def table_ddl(name):
    sk, nk, attrs, _ = SPECS[name]
    definitions = []
    for col, kind in fields(name):
        definitions.append(s.ident(col) + ' ' + kind + (' COLLATE "C"' if kind == 'text' else '') +
                           (' NOT NULL' if col in (sk, 'membro_tipo') else ''))
    definitions += [f'CONSTRAINT {s.ident(name+"_pkey")} PRIMARY KEY ({s.ident(sk)})',
                    f'CONSTRAINT {s.ident(name+"_nk")} UNIQUE (' + ','.join(s.ident(n) for n, _ in nk) + ')']
    absent = ' AND '.join(s.ident(n) + ' IS NULL' for n, _ in nk + attrs)
    present = ' AND '.join(s.ident(n) + ' IS NOT NULL' for n, _ in nk)
    check = (f"(({s.ident(sk)}=-1 AND membro_tipo='nao_informado' AND {absent}) OR "
             f"({s.ident(sk)}=-2 AND membro_tipo='referencia_nao_encontrada' AND {absent}) OR "
             f"({s.ident(sk)}>0 AND membro_tipo='regular' AND {present}))")
    definitions.append(f'CONSTRAINT {s.ident(name+"_membros")} CHECK ({check})')
    return f'CREATE TABLE IF NOT EXISTS {tbl(name)} (\n  ' + ',\n  '.join(definitions) + '\n);\n'


def marker(name):
    return MARKER + ':' + hashlib.sha256(table_ddl(name).encode()).hexdigest()


def guard():
    """Adaptação local da allowlist da etapa 4A; o arquivo validado não é alterado."""
    sql = s.guard_sql()
    old = "nspname NOT IN ('information_schema','public','silver')"
    if sql.count(old) != 1:
        raise s.SilverError('Proteção Silver mudou: revisar allowlist antes de prosseguir.')
    sql = sql.replace(old, "nspname NOT IN ('information_schema','public','silver','gold')")
    start = "AND NOT (n.nspname='silver' AND c.relname IN ("
    position = sql.index(start)
    end = sql.index("AND c.relkind IN ('r','i')))", position)
    ending = "AND c.relkind IN ('r','i')))"
    names = [name for n in SPECS for name in (n, n + '_pkey', n + '_nk')]
    original=sql[position:end+len(ending)]
    silver_condition=original[len('AND NOT ('):-2]
    table_names=','.join(s.literal(n) for n in SPECS)
    index_names=','.join(s.literal(n) for n in names if n not in SPECS)
    gold_condition=("n.nspname='gold' AND ((c.relkind='r' AND c.relname IN ("+table_names+
                    ")) OR (c.relkind='i' AND c.relname IN ("+index_names+")))")
    replacement='AND NOT (('+silver_condition+') OR ('+gold_condition+')))'
    sql=sql[:position]+replacement+sql[end+len(ending):]
    extra = f"""DO $gold_guard$ BEGIN
 IF current_database() <> 'inteligencia_receita_db' THEN RAISE EXCEPTION 'Banco fora do projeto'; END IF;
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='gold' AND
  (obj_description(oid,'pg_namespace') IS DISTINCT FROM {s.literal(MARKER)} OR pg_get_userbyid(nspowner)<>current_user))
 THEN RAISE EXCEPTION 'Schema gold preexistente não reconhecido'; END IF;
 IF EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='gold' AND NOT t.tgisinternal)
 OR EXISTS (SELECT 1 FROM pg_rewrite r JOIN pg_class c ON c.oid=r.ev_class JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='gold')
 OR EXISTS (SELECT 1 FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='gold')
 THEN RAISE EXCEPTION 'Comportamento não previsto na Gold'; END IF;
"""
    for name in SPECS:
        spec = [dict(name=n, type=t, required=n in (SPECS[name][0], 'membro_tipo')) for n, t in fields(name)]
        reg = s.literal('gold.' + name)
        nk = ', '.join(n for n, _ in SPECS[name][1])
        extra += f"""
 IF to_regclass({reg}) IS NOT NULL THEN
  IF NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.oid=to_regclass({reg}) AND c.relkind='r'
   AND NOT c.relrowsecurity AND NOT c.relispartition AND pg_get_userbyid(c.relowner)=current_user
   AND obj_description(c.oid,'pg_class')={s.literal(marker(name))})
  OR (SELECT jsonb_agg(jsonb_build_object('name',attname,'type',format_type(atttypid,atttypmod),'required',attnotnull) ORDER BY attnum)
   FROM pg_attribute WHERE attrelid=to_regclass({reg}) AND attnum>0 AND NOT attisdropped) IS DISTINCT FROM {s.literal(json.dumps(spec))}::jsonb
  OR EXISTS (SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass({reg}))
  OR EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass({reg}) AND attnum>0 AND NOT attisdropped
    AND atttypid='text'::regtype AND attcollation <> '"C"'::regcollation)
  OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass({reg}) AND contype<>'n')<>3
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass({reg}) AND contype='p'
     AND pg_get_constraintdef(oid)={s.literal('PRIMARY KEY ('+SPECS[name][0]+')')})
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass({reg}) AND contype='u'
     AND pg_get_constraintdef(oid)={s.literal('UNIQUE ('+nk+')')})
  OR NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass({reg}) AND contype='c'
     AND conname={s.literal(name+'_membros')} AND convalidated)
  THEN RAISE EXCEPTION 'Dimensão preexistente incompatível: {name}'; END IF;
 END IF;
"""
    return sql + extra + 'END $gold_guard$;\n'


def source_checks():
    sql = 'DO $source$ BEGIN\n'
    for entity, key in [('customers', 'customer_id'), ('products', 'product_id'),
                        ('sellers', 'seller_id'), ('translation', 'product_category_name')]:
        sql += f"IF EXISTS(SELECT {s.ident(key)} FROM {s.table(entity)} GROUP BY {s.ident(key)} HAVING count(*)>1) THEN "
        sql += f"RAISE EXCEPTION 'Chave Silver ambígua: {entity}.{key}'; END IF;\n"
    sql += "IF EXISTS (SELECT 1 FROM silver.olist_orders_dataset o WHERE o.customer_id IS NOT NULL AND NOT EXISTS "
    sql += "(SELECT 1 FROM silver.olist_customers_dataset c WHERE c.customer_id=o.customer_id)) THEN RAISE EXCEPTION 'Contexto de cliente não resolvido'; END IF;\n"
    return sql + 'END $source$;\n'


def ddl():
    out = '-- Executar via gold_dimensoes.py; validações e transação são obrigatórias.\n' + guard() + source_checks()
    out += 'CREATE SCHEMA IF NOT EXISTS gold;\n' + f'COMMENT ON SCHEMA gold IS {s.literal(MARKER)};\n'
    for name in SPECS:
        out += table_ddl(name) + f'COMMENT ON TABLE {tbl(name)} IS {s.literal(marker(name))};\n'
    return out


def load():
    out = '-- Sem substituição da Silver ou atualização silenciosa de atributos.\n'
    for name in SPECS:
        cols = ','.join(s.ident(n) for n, _ in fields(name))
        out += f'INSERT INTO {tbl(name)} ({cols}) {expected(name)} ON CONFLICT ({s.ident(SPECS[name][0])}) DO NOTHING;\n'
    return out


def resolution_sources():
    customer = 'silver.olist_customers_dataset'
    orders = 'silver.olist_orders_dataset'
    loc = ('d.customer_zip_code_prefix=c.customer_zip_code_prefix AND '
           'd.customer_city=c.customer_city AND d.customer_state=c.customer_state')
    mapping = {
        'pedidos_cliente': (f'{orders} o LEFT JOIN {customer} c ON c.customer_id=o.customer_id '
                           'LEFT JOIN gold.dim_clientes d ON d.customer_unique_id=c.customer_unique_id',
                           "CASE WHEN o.customer_id IS NULL THEN -1 WHEN c.customer_id IS NULL THEN -2 WHEN c.customer_unique_id IS NULL THEN -1 ELSE COALESCE(d.cliente_sk,-2) END",
                           'SELECT count(*) FROM ' + orders),
        'pedidos_localizacao': (f'{orders} o LEFT JOIN {customer} c ON c.customer_id=o.customer_id '
                               f'LEFT JOIN gold.dim_localizacao d ON {loc}',
                               "CASE WHEN o.customer_id IS NULL THEN -1 WHEN c.customer_id IS NULL THEN -2 "
                               "WHEN c.customer_zip_code_prefix IS NULL OR c.customer_city IS NULL OR c.customer_state IS NULL THEN -1 ELSE COALESCE(d.localizacao_sk,-2) END",
                               'SELECT count(*) FROM ' + orders),
        'pagamentos_forma': ('silver.olist_order_payments_dataset p LEFT JOIN gold.dim_forma_pagamento d ON d.payment_type=p.payment_type',
                            'CASE WHEN p.payment_type IS NULL THEN -1 ELSE COALESCE(d.forma_pagamento_sk,-2) END',
                            'SELECT count(*) FROM silver.olist_order_payments_dataset'),
    }
    for label, field, dim, key in [('itens_produto','product_id','dim_produtos','produto_sk'),
                                    ('itens_vendedor','seller_id','dim_vendedores','vendedor_sk')]:
        mapping[label] = (f'silver.olist_order_items_dataset i LEFT JOIN gold.{dim} d ON d.{field}=i.{field}',
                          f'CASE WHEN i.{field} IS NULL THEN -1 ELSE COALESCE(d.{key},-2) END',
                          'SELECT count(*) FROM silver.olist_order_items_dataset')
    for entity,label in [('items','itens'),('payments','pagamentos')]:
        count='SELECT count(*) FROM '+s.table(entity)
        base=f'{s.table(entity)} child LEFT JOIN {orders} o ON o.order_id=child.order_id '
        for suffix,original in [('cliente','pedidos_cliente'),('localizacao','pedidos_localizacao')]:
            query,expr,_=mapping[original]
            suffix_query=query.split(orders+' o ',1)[1]
            mapping[label+'_'+suffix]=(base+suffix_query,
                'CASE WHEN child.order_id IS NULL THEN -1 WHEN o.order_id IS NULL THEN -2 ELSE ('+expr+') END',count)
        mapping['calendario_compra_'+label]=(
            base+'LEFT JOIN gold.dim_calendario d ON d.dia=o.order_purchase_timestamp::date',
            'CASE WHEN child.order_id IS NULL THEN -1 WHEN o.order_id IS NULL THEN -2 WHEN o.order_purchase_timestamp IS NULL THEN -1 ELSE COALESCE(d.data_sk,-2) END',count)
    for entity, field in ROLES:
        mapping['calendario_' + field] = (f'{s.table(entity)} src LEFT JOIN gold.dim_calendario d ON d.dia=src.{s.ident(field)}::date',
                                          f'CASE WHEN src.{s.ident(field)} IS NULL THEN -1 ELSE COALESCE(d.data_sk,-2) END',
                                          'SELECT count(*) FROM ' + s.table(entity))
    return mapping


def validation():
    out = 'DO $validation$ BEGIN\n'
    for name in SPECS:
        cols = ','.join(s.ident(n) for n, _ in fields(name))
        out += f"IF EXISTS ((SELECT {cols} FROM {tbl(name)} EXCEPT ALL SELECT * FROM ({expected(name)}) e) "
        out += f"UNION ALL (SELECT * FROM ({expected(name)}) e EXCEPT ALL SELECT {cols} FROM {tbl(name)})) "
        out += f"THEN RAISE EXCEPTION 'Conteúdo, atributos ou SK divergentes: {name}'; END IF;\n"
    for label, (query, expr, count) in resolution_sources().items():
        out += f"IF (SELECT count(*) FROM {query}) <> ({count}) OR EXISTS(SELECT 1 FROM {query} WHERE ({expr})=-2) "
        out += f"THEN RAISE EXCEPTION 'Resolução ou cardinalidade divergente: {label}'; END IF;\n"
    out += "IF EXISTS(SELECT 1 FROM silver.olist_order_payments_dataset p LEFT JOIN gold.dim_forma_pagamento d USING(payment_type) "
    out += "WHERE p.payment_type='not_defined' AND (d.forma_pagamento_sk IS NULL OR d.forma_pagamento_sk<1 OR d.membro_tipo<>'regular')) "
    out += "THEN RAISE EXCEPTION 'not_defined deixou de ser método da origem'; END IF;\n"
    return out + 'END $validation$;\n'


def constraint_tests():
    out='DO $constraint_tests$ BEGIN\n'
    for name in SPECS:
        sk=SPECS[name][0]
        cols=','.join(s.ident(n) for n,_ in fields(name))
        # Consulta sintética: nenhum cadastro fictício deve ser persistido.
        nulls=','.join('NULL::'+t for _,t in SPECS[name][1]+SPECS[name][2])
        out+=f"BEGIN INSERT INTO {tbl(name)} ({cols}) SELECT COALESCE(max({s.ident(sk)}),0)+1,{nulls},'regular' FROM {tbl(name)}; "
        out+=f"RAISE EXCEPTION 'Aceitou identidade regular nula: {name}'; EXCEPTION WHEN check_violation THEN NULL; END;\n"
        projection=','.join('src.'+s.ident(n) for n,_ in fields(name)[1:])
        out+=f"IF EXISTS(SELECT 1 FROM {tbl(name)} WHERE membro_tipo='regular') THEN BEGIN "
        out+=f"INSERT INTO {tbl(name)} ({cols}) SELECT (SELECT max({s.ident(sk)})+1 FROM {tbl(name)}),{projection} FROM {tbl(name)} src WHERE membro_tipo='regular' LIMIT 1; "
        out+=f"RAISE EXCEPTION 'Aceitou chave natural repetida: {name}'; EXCEPTION WHEN unique_violation THEN NULL; END; END IF;\n"
    out+="IF (SELECT count(*) FROM gold.dim_clientes WHERE cliente_sk IN (-1,-2))<>2 THEN RAISE EXCEPTION 'Membros especiais ausentes'; END IF;\n"
    out+="IF (SELECT CASE WHEN v.id IS NULL THEN -1 ELSE COALESCE(d.cliente_sk,-2) END FROM (VALUES(NULL::text)) v(id) LEFT JOIN gold.dim_clientes d ON d.customer_unique_id=v.id)<>-1 THEN RAISE EXCEPTION 'Nulo não resolve NI'; END IF;\n"
    out+="IF EXISTS(SELECT 1 FROM gold.dim_clientes WHERE customer_unique_id='__referencia_sintetica__') THEN RAISE EXCEPTION 'Fixture sintética colide com origem'; END IF;\n"
    out+="IF (SELECT COALESCE(d.cliente_sk,-2) FROM (VALUES('__referencia_sintetica__'::text)) v(id) LEFT JOIN gold.dim_clientes d ON d.customer_unique_id=v.id)<>-2 THEN RAISE EXCEPTION 'Referência ausente não resolve REF'; END IF;\n"
    return out+'END $constraint_tests$;\n'


def observations(include_gold=True):
    out = ''
    for name in SPECS:
        out += f"SELECT json_build_object('dimension',{s.literal(name)},'source_distinct',count(*)) FROM ({source(name)}) x;\n"
        if include_gold:
            cols = ','.join(s.ident(n) for n, _ in fields(name))
            out += f"SELECT json_build_object('dimension',{s.literal(name)},'rows',count(*),'regular',count(*) FILTER(WHERE membro_tipo='regular'),"
            out += "'nao_informado',count(*) FILTER(WHERE membro_tipo='nao_informado'),'referencia_nao_encontrada',count(*) FILTER(WHERE membro_tipo='referencia_nao_encontrada'),"
            out += f"'fingerprint',encode(sha256(convert_to(string_agg(row_to_json(x)::text,'' ORDER BY {s.ident(SPECS[name][0])}),'UTF8')),'hex')) "
            out += f'FROM (SELECT {cols} FROM {tbl(name)}) x;\n'
    out += "SELECT json_build_object('calendar_min',min(dia),'calendar_max',max(dia),'observed_distinct_days',count(DISTINCT dia)) FROM (" + calendar_days() + ') d;\n'
    out += "SELECT json_build_object('products_category_null',count(*) FILTER(WHERE p.product_category_name IS NULL),'products_translation_missing',count(*) FILTER(WHERE p.product_category_name IS NOT NULL AND t.product_category_name IS NULL)) FROM silver.olist_products_dataset p LEFT JOIN silver.product_category_name_translation t USING(product_category_name);\n"
    out += "SELECT json_build_object('partial_locations',count(*)) FROM silver.olist_orders_dataset o JOIN silver.olist_customers_dataset c USING(customer_id) WHERE c.customer_zip_code_prefix IS NULL OR c.customer_city IS NULL OR c.customer_state IS NULL;\n"
    if include_gold:
        for label, (query, expr, _) in resolution_sources().items():
            out += f"SELECT json_build_object('resolution',{s.literal(label)},'rows',count(*),'regular',count(*) FILTER(WHERE ({expr})>0),"
            out += f"'nao_informado',count(*) FILTER(WHERE ({expr})=-1),'referencia_nao_encontrada',count(*) FILTER(WHERE ({expr})=-2)) FROM {query};\n"
    return out


def prefix(readonly=False):
    return s.transaction_prefix(readonly).replace('BEGIN READ ONLY;', 'BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;').replace('BEGIN;', 'BEGIN ISOLATION LEVEL REPEATABLE READ;')


def locks():
    return 'SELECT pg_advisory_xact_lock(871204031);\nLOCK TABLE ' + ','.join(s.table(e) for e in s.TABLES) + ' IN SHARE MODE;\n'


def run_sql(work, name, text):
    path = work / (name + '.sql')
    path.write_text(text, encoding='utf-8')
    return s.run_psql(path)


def run(output, mode='run'):
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status='started',mode=mode,started_utc=datetime.now(timezone.utc).isoformat(),errors=[],runs={})
    try:
        if os.environ.get('PGDATABASE') != 'inteligencia_receita_db' or s.environment_status()['blockers']:
            raise s.SilverError('Conexão explícita protegida não disponível para inteligencia_receita_db.')
        approved = json.loads((EVIDENCE/'integracao/verify/resultado.json').read_text(encoding='utf-8'))
        if approved['status'] != 'verified_readonly':
            raise s.SilverError('Evidência Silver incompatível.')
        for entity, st in approved['sources'].items():
            if s.sha256(s.ROOT/'data/bronze'/st['file']) != st['sha256']:
                raise s.SilverError('Bronze diferente da versão Silver validada.')
        for filename, generated in [('001_dimensoes.sql',ddl()),('002_carga_dimensoes.sql',load())]:
            if (s.ROOT/'sql/gold'/filename).read_text(encoding='utf-8') != generated:
                raise s.SilverError('DDL/carga divergem do gerador revisado.')
        if (s.ROOT/'sql/validacoes/gold_dimensoes.sql').read_text(encoding='utf-8') != validation()+observations():
            raise s.SilverError('SQL de validação divergente.')
        with tempfile.TemporaryDirectory(prefix='olist_gold_') as folder:
            work=Path(folder)
            compatible=guard()+source_checks()+s.validation_sql(approved['sources'])
            identity="SELECT json_build_object('database',current_database(),'version',current_setting('server_version'),'encoding',current_setting('server_encoding'),'isolated',true);\n"
            report['preflight']=run_sql(work,'preflight',prefix(True)+compatible+identity+observations(False)+'ROLLBACK;\n')
            print('Destino e Silver validados; quantitativos naturais calculados.',flush=True)
            if mode == 'inspect':
                report['status']='inspected_readonly'
            else:
                for name, rollback in [('first',False),('second',False),('rollback',True)]:
                    statements=prefix()+locks()+guard()+source_checks()
                    statements+=(s.ROOT/'sql/gold/001_dimensoes.sql').read_text(encoding='utf-8')
                    statements+=(s.ROOT/'sql/gold/002_carga_dimensoes.sql').read_text(encoding='utf-8')
                    statements+=guard()+validation()+observations()
                    statements+=constraint_tests()
                    if rollback:
                        # Remove um membro técnico só na transação que deverá ser revertida.
                        statements+="DELETE FROM gold.dim_clientes WHERE cliente_sk=-2;\n"
                        statements+="DO $canary$ BEGIN IF EXISTS(SELECT 1 FROM gold.dim_clientes WHERE cliente_sk=-2) THEN RAISE EXCEPTION 'Canário não aplicado'; END IF; END $canary$;\nSELECT 1/0;\n"
                    statements+='COMMIT;\n'
                    try:
                        result=run_sql(work,name,statements)
                        if rollback:
                            raise s.SilverError('Falha deliberada não ocorreu.')
                        report['runs'][name]=dict(status='committed',results=result)
                    except s.SilverError as exc:
                        if not rollback or 'SQLSTATE 22012' not in str(exc):
                            raise
                        report['runs'][name]=dict(status='expected_failure',sqlstate='22012')
                    (output/(name+'.json')).write_text(json.dumps(report['runs'][name],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    print('Etapa '+name+': '+report['runs'][name]['status'],flush=True)
                report['after']=run_sql(work,'verify',prefix(True)+compatible+validation()+observations()+s.observation_sql()+'ROLLBACK;\n')
                report['idempotence']=report['runs']['first']['results']==report['runs']['second']['results']
                # A parte Gold do relatório pós-rollback deve ser idêntica à segunda carga.
                expected_count=len(report['runs']['second']['results'])
                report['rollback_confirmed']=report['after'][:expected_count]==report['runs']['second']['results']
                if not report['idempotence'] or not report['rollback_confirmed']:
                    raise s.SilverError('Idempotência ou rollback divergente.')
                report['silver_preserved']=True
                report['status']='completed_verified'
        report['bronze_preserved']=all(s.sha256(s.ROOT/'data/bronze'/st['file'])==st['sha256'] for st in approved['sources'].values())
    except Exception as exc:
        report['status']='failed'
        report['errors'].append(str(exc) if isinstance(exc,s.SilverError) else type(exc).__name__)
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    (output/'resultado.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'execucao.log').write_text('\n'.join([report['started_utc'],'mode='+mode,'status='+report['status']]+report['errors'])+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('inspect','run'),default='run')
    parser.add_argument('--output',type=Path,default=s.ROOT/'docs/qualidade/etapa4_gold_dimensoes'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    args=parser.parse_args()
    result=run(args.output.resolve(),args.mode)
    print(json.dumps(dict(status=result['status'],errors=result['errors'],output=str(args.output)),ensure_ascii=True))
    raise SystemExit(0 if not result['errors'] else 1)


if __name__=='__main__':
    main()
