"""Etapa 4C: três fatos; dimensões existentes e Silver são apenas consultadas."""
import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import gold_dimensoes as d
import silver as s

MARKER = 'inteligencia_receita:gold_fatos:v1'
DIM_EVIDENCE = s.ROOT / 'docs/qualidade/etapa4_gold_dimensoes/20261108T033107805228Z'
SPECS = {
    'fato_pedidos': ('orders', ('order_id',)),
    'fato_itens_pedido': ('items', ('order_id', 'order_item_id')),
    'fato_pagamentos': ('payments', ('order_id', 'payment_sequential')),
}
ORDER_DATES = {
    'order_purchase_timestamp': 'data_compra_sk',
    'order_approved_at': 'data_aprovacao_sk',
    'order_delivered_carrier_date': 'data_transportadora_sk',
    'order_delivered_customer_date': 'data_entrega_sk',
    'order_estimated_delivery_date': 'data_previsao_entrega_sk',
}


def fks(name):
    result = [('cliente_sk', 'dim_clientes', 'cliente_sk'),
              ('localizacao_sk', 'dim_localizacao', 'localizacao_sk')]
    if name == 'fato_pedidos':
        result += [(col, 'dim_calendario', 'data_sk') for col in ORDER_DATES.values()]
    elif name == 'fato_itens_pedido':
        result += [('produto_sk', 'dim_produtos', 'produto_sk'),
                   ('vendedor_sk', 'dim_vendedores', 'vendedor_sk'),
                   ('data_compra_sk', 'dim_calendario', 'data_sk'),
                   ('data_limite_envio_sk', 'dim_calendario', 'data_sk')]
    else:
        result += [('forma_pagamento_sk', 'dim_forma_pagamento', 'forma_pagamento_sk'),
                   ('data_compra_sk', 'dim_calendario', 'data_sk')]
    return result


def fields(name):
    entity, _ = SPECS[name]
    result = list(s.columns(entity))
    if entity != 'orders':
        result += [('customer_id', 'text'), ('order_status', 'text'),
                   ('order_purchase_timestamp', 'timestamp without time zone')]
    return result + [(col, 'bigint') for col, _, _ in fks(name)]


def table(name):
    return 'gold.' + s.ident(name)


def fk_name(name, col):
    prefix = {'fato_pedidos': 'fp', 'fato_itens_pedido': 'fip', 'fato_pagamentos': 'fpg'}[name]
    return prefix + '_' + col + '_fk'


def ddl_table(name):
    _, pk = SPECS[name]
    required = set(pk) | {col for col, _, _ in fks(name)}
    definitions = [s.ident(col) + ' ' + kind + (' COLLATE "C"' if kind == 'text' else '') +
                   (' NOT NULL' if col in required else '') for col, kind in fields(name)]
    definitions.append('CONSTRAINT ' + s.ident(name + '_pkey') + ' PRIMARY KEY (' +
                       ','.join(s.ident(col) for col in pk) + ')')
    for col, dim, key in fks(name):
        definitions.append(f'CONSTRAINT {s.ident(fk_name(name,col))} FOREIGN KEY ({s.ident(col)}) '
                           f'REFERENCES gold.{s.ident(dim)} ({s.ident(key)}) ON UPDATE NO ACTION ON DELETE NO ACTION NOT DEFERRABLE')
    return f'CREATE TABLE IF NOT EXISTS {table(name)} (\n  ' + ',\n  '.join(definitions) + '\n);\n'


def marker(name):
    return MARKER + ':' + hashlib.sha256(ddl_table(name).encode()).hexdigest()


def guard():
    """Amplia apenas a allowlist local da fase anterior, sem modificar seus arquivos."""
    sql = d.guard()
    for kind, old_names, extra_names in [
        ('r', list(d.SPECS), list(SPECS)),
        ('i', [n for dim in d.SPECS for n in (dim+'_pkey', dim+'_nk')], [n+'_pkey' for n in SPECS]),
    ]:
        old = "c.relkind='" + kind + "' AND c.relname IN (" + ','.join(s.literal(n) for n in old_names) + ')'
        new = old[:-1] + ',' + ','.join(s.literal(n) for n in extra_names) + ')'
        if sql.count(old) != 1:
            raise s.SilverError('Proteção anterior mudou; revisar allowlist da etapa 4C.')
        sql = sql.replace(old, new)
    extra = 'DO $fact_guard$ BEGIN\n'
    for name, (_, pk) in SPECS.items():
        reg = s.literal('gold.' + name)
        required = set(pk) | {col for col, _, _ in fks(name)}
        shape = [dict(name=n, type=t, required=n in required) for n, t in fields(name)]
        extra += f"""
IF to_regclass({reg}) IS NOT NULL THEN
 IF NOT EXISTS(SELECT 1 FROM pg_class c WHERE c.oid=to_regclass({reg}) AND c.relkind='r'
  AND NOT c.relrowsecurity AND NOT c.relispartition AND pg_get_userbyid(c.relowner)=current_user
  AND obj_description(c.oid,'pg_class')={s.literal(marker(name))})
 OR (SELECT jsonb_agg(jsonb_build_object('name',attname,'type',format_type(atttypid,atttypmod),'required',attnotnull) ORDER BY attnum)
  FROM pg_attribute WHERE attrelid=to_regclass({reg}) AND attnum>0 AND NOT attisdropped) IS DISTINCT FROM {s.literal(json.dumps(shape))}::jsonb
 OR EXISTS(SELECT 1 FROM pg_attrdef WHERE adrelid=to_regclass({reg}))
 OR EXISTS(SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass({reg}) AND attnum>0 AND NOT attisdropped
  AND atttypid='text'::regtype AND attcollation <> '"C"'::regcollation)
 OR (SELECT count(*) FROM pg_constraint WHERE conrelid=to_regclass({reg}) AND contype<>'n') <> {1+len(fks(name))}
 OR NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid=to_regclass({reg}) AND contype='p'
  AND pg_get_constraintdef(oid)={s.literal('PRIMARY KEY ('+', '.join(pk)+')')})
 THEN RAISE EXCEPTION 'Fato preexistente incompatível: {name}'; END IF;
"""
        for col, dim, key in fks(name):
            extra += f"""IF NOT EXISTS(SELECT 1 FROM pg_constraint k
 WHERE k.conrelid=to_regclass({reg}) AND k.contype='f' AND k.conname={s.literal(fk_name(name,col))}
 AND k.confrelid='gold.{dim}'::regclass AND k.convalidated AND NOT k.condeferrable
 AND k.confupdtype='a' AND k.confdeltype='a' AND k.confmatchtype='s'
 AND k.conkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid=k.conrelid AND attname={s.literal(col)})]::smallint[]
 AND k.confkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid=k.confrelid AND attname={s.literal(key)})]::smallint[])
 THEN RAISE EXCEPTION 'FK ausente ou incompatível: {name}.{col}'; END IF;
"""
        extra += 'END IF;\n'
    return sql + extra + 'END $fact_guard$;\n'


def expected(name):
    entity, _ = SPECS[name]
    base_alias = 'o' if entity == 'orders' else 'src'
    joins = f'{s.table(entity)} {base_alias} '
    if entity != 'orders':
        joins += 'LEFT JOIN silver.olist_orders_dataset o ON o.order_id=src.order_id '
    joins += 'LEFT JOIN silver.olist_customers_dataset c ON c.customer_id=o.customer_id '
    joins += 'LEFT JOIN gold.dim_clientes dc ON dc.customer_unique_id=c.customer_unique_id '
    joins += ('LEFT JOIN gold.dim_localizacao dl ON dl.customer_zip_code_prefix=c.customer_zip_code_prefix '
              'AND dl.customer_city=c.customer_city AND dl.customer_state=c.customer_state ')
    values = [base_alias+'.'+s.ident(col) for col, _ in s.columns(entity)]
    if entity != 'orders':
        values += ['o.customer_id', 'o.order_status', 'o.order_purchase_timestamp']
    parent = '' if entity == 'orders' else 'WHEN o.order_id IS NULL THEN -2 '
    projections = {
        'cliente_sk': f'CASE {parent}WHEN o.customer_id IS NULL THEN -1 WHEN c.customer_id IS NULL THEN -2 '
                      'WHEN c.customer_unique_id IS NULL THEN -1 ELSE COALESCE(dc.cliente_sk,-2) END',
        'localizacao_sk': f'CASE {parent}WHEN o.customer_id IS NULL THEN -1 WHEN c.customer_id IS NULL THEN -2 '
                         'WHEN c.customer_zip_code_prefix IS NULL OR c.customer_city IS NULL OR c.customer_state IS NULL '
                         'THEN -1 ELSE COALESCE(dl.localizacao_sk,-2) END',
    }
    if entity == 'items':
        joins += 'LEFT JOIN gold.dim_produtos dp ON dp.product_id=src.product_id '
        joins += 'LEFT JOIN gold.dim_vendedores dv ON dv.seller_id=src.seller_id '
        projections['produto_sk'] = 'CASE WHEN src.product_id IS NULL THEN -1 ELSE COALESCE(dp.produto_sk,-2) END'
        projections['vendedor_sk'] = 'CASE WHEN src.seller_id IS NULL THEN -1 ELSE COALESCE(dv.vendedor_sk,-2) END'
    elif entity == 'payments':
        joins += 'LEFT JOIN gold.dim_forma_pagamento df ON df.payment_type=src.payment_type '
        projections['forma_pagamento_sk'] = 'CASE WHEN src.payment_type IS NULL THEN -1 ELSE COALESCE(df.forma_pagamento_sk,-2) END'
    dates = list(ORDER_DATES.items()) if entity == 'orders' else [('order_purchase_timestamp','data_compra_sk')]
    if entity == 'items':
        dates += [('shipping_limit_date','data_limite_envio_sk')]
    for index, (field, fk) in enumerate(dates):
        origin = 'src' if field == 'shipping_limit_date' else 'o'
        alias = 'dt'+str(index)
        joins += f'LEFT JOIN gold.dim_calendario {alias} ON {alias}.dia={origin}.{s.ident(field)}::date '
        missing_parent = parent if field != 'shipping_limit_date' else ''
        projections[fk] = f'CASE {missing_parent}WHEN {origin}.{s.ident(field)} IS NULL THEN -1 ELSE COALESCE({alias}.data_sk,-2) END'
    values += [projections[col]+'::bigint AS '+s.ident(col) for col, _, _ in fks(name)]
    return 'SELECT '+','.join(values)+' FROM '+joins


def source_checks():
    out = d.source_checks()+'DO $source_facts$ BEGIN\n'
    for name, (entity, pk) in SPECS.items():
        cols = ','.join(s.ident(n) for n in pk)
        missing = ' OR '.join(s.ident(n)+' IS NULL' for n in pk)
        out += f"IF EXISTS(SELECT 1 FROM {s.table(entity)} WHERE {missing}) OR EXISTS(SELECT {cols} FROM {s.table(entity)} GROUP BY {cols} HAVING count(*)>1) "
        out += f"THEN RAISE EXCEPTION 'Grão Silver inválido: {name}'; END IF;\n"
        out += f"IF (SELECT count(*) FROM ({expected(name)}) e) <> (SELECT count(*) FROM {s.table(entity)}) "
        out += f"THEN RAISE EXCEPTION 'Lookup multiplicou ou excluiu linhas: {name}'; END IF;\n"
    return out+'END $source_facts$;\n'


def ddl():
    out = '-- Etapa 4C: executar pelo orquestrador transacional; não cria ou altera dimensões.\n'+guard()+source_checks()
    for name in SPECS:
        out += ddl_table(name)+f'COMMENT ON TABLE {table(name)} IS {s.literal(marker(name))};\n'
    return out


def load():
    out = '-- Um SELECT independente por grão, sem filtro de status e sem rateios.\n'
    for name, (_, pk) in SPECS.items():
        cols = ','.join(s.ident(n) for n, _ in fields(name))
        out += f'INSERT INTO {table(name)} ({cols}) {expected(name)} WHERE TRUE ON CONFLICT ('+','.join(s.ident(n) for n in pk)+') DO NOTHING;\n'
    return out


def reconciliation(layer):
    orders, items, payments = ((s.table('orders'),s.table('items'),s.table('payments')) if layer == 'silver'
                               else (table('fato_pedidos'),table('fato_itens_pedido'),table('fato_pagamentos')))
    return f"""WITH i AS (SELECT order_id,count(*) itens,sum(price) preco,sum(freight_value) frete FROM {items} GROUP BY order_id),
p AS (SELECT order_id,count(*) pagamentos,sum(payment_value) valor FROM {payments} GROUP BY order_id)
SELECT o.order_id,o.order_status,i.itens,p.pagamentos,i.preco,i.frete,p.valor,
 CASE WHEN i.order_id IS NULL OR p.order_id IS NULL THEN NULL ELSE p.valor-i.preco-i.frete END diferenca
FROM {orders} o LEFT JOIN i ON i.order_id=o.order_id LEFT JOIN p ON p.order_id=o.order_id"""


def validation():
    out = 'DO $fact_validation$ BEGIN\n'
    for name, (entity, pk) in SPECS.items():
        cols = ','.join(s.ident(n) for n, _ in fields(name))
        out += f"IF EXISTS((SELECT {cols} FROM {table(name)} EXCEPT ALL {expected(name)}) UNION ALL "
        out += f"({expected(name)} EXCEPT ALL SELECT {cols} FROM {table(name)})) THEN RAISE EXCEPTION 'Conteúdo ou resolução divergente: {name}'; END IF;\n"
        out += f"IF (SELECT count(*) FROM {table(name)}) <> (SELECT count(*) FROM {s.table(entity)}) THEN RAISE EXCEPTION 'Contagem divergente: {name}'; END IF;\n"
        for col, dim, key in fks(name):
            out += f"IF EXISTS(SELECT 1 FROM {table(name)} f WHERE NOT EXISTS(SELECT 1 FROM gold.{s.ident(dim)} d WHERE d.{s.ident(key)}=f.{s.ident(col)})) "
            out += f"THEN RAISE EXCEPTION 'FK órfã: {name}.{col}'; END IF;\n"
        for col, kind in s.columns(entity):
            if col in ('price','freight_value','payment_value'):
                out += f"IF (SELECT sum({s.ident(col)}) FROM {table(name)}) IS DISTINCT FROM (SELECT sum({s.ident(col)}) FROM {s.table(entity)}) "
                out += f"THEN RAISE EXCEPTION 'Soma exata divergente: {name}.{col}'; END IF;\n"
    gold = reconciliation('gold')
    silver = reconciliation('silver')
    out += f"IF EXISTS((SELECT * FROM ({gold}) a EXCEPT ALL SELECT * FROM ({silver}) b) UNION ALL "
    out += f"(SELECT * FROM ({silver}) b EXCEPT ALL SELECT * FROM ({gold}) a)) THEN RAISE EXCEPTION 'Reconciliação por pedido divergente'; END IF;\n"
    return out+'END $fact_validation$;\n'


def constraint_tests():
    out = 'DO $fact_constraint_tests$ BEGIN\n'
    for name, (_, pk) in SPECS.items():
        order = ','.join(s.ident(n) for n in pk)
        out += f"BEGIN INSERT INTO {table(name)} SELECT * FROM {table(name)} ORDER BY {order} LIMIT 1; "
        out += f"RAISE EXCEPTION 'PK aceitou repetição: {name}'; EXCEPTION WHEN unique_violation THEN NULL; END;\n"
        condition = '('+order+')=(SELECT '+order+f' FROM {table(name)} ORDER BY {order} LIMIT 1)'
        out += f"BEGIN UPDATE {table(name)} SET {s.ident(pk[0])}=NULL WHERE {condition}; "
        out += f"RAISE EXCEPTION 'PK aceitou nulo: {name}'; EXCEPTION WHEN not_null_violation THEN NULL; END;\n"
        for col, dim, key in fks(name):
            out += f"BEGIN UPDATE {table(name)} SET {s.ident(col)}=(SELECT max({s.ident(key)})+1 FROM gold.{s.ident(dim)}) WHERE {condition}; "
            out += f"RAISE EXCEPTION 'FK aceitou referência inexistente: {name}.{col}'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;\n"
    return out+'END $fact_constraint_tests$;\n'


def observations():
    out = ''
    for name, (entity, pk) in SPECS.items():
        cols = ','.join(s.ident(n) for n, _ in fields(name))
        order = ','.join(s.ident(n) for n in pk)
        money = ','.join(s.literal(n)+',sum('+s.ident(n)+')::text' for n, _ in fields(name) if n in ('price','freight_value','payment_value'))
        members = ','.join(s.literal(col)+",json_build_object('nao_informado',count(*) FILTER(WHERE "+s.ident(col)+"=-1),'referencia_nao_encontrada',count(*) FILTER(WHERE "+s.ident(col)+"=-2))" for col, _, _ in fks(name))
        out += f"SELECT json_build_object('fact',{s.literal(name)},'silver_rows',(SELECT count(*) FROM {s.table(entity)}),'rows',count(*),"
        out += f"'money',json_build_object({money}),'fk_members',json_build_object({members}),"
        out += f"'fingerprint',encode(sha256(convert_to(string_agg(row_to_json(x)::text,'' ORDER BY {order}),'UTF8')),'hex')) FROM (SELECT {cols} FROM {table(name)}) x;\n"
        out += f"SELECT json_build_object('fact',{s.literal(name)},'statuses',json_object_agg(order_status,n)) FROM (SELECT order_status,count(*) n FROM {table(name)} GROUP BY order_status) q;\n"
    out += "SELECT json_build_object('reconciliation_orders',count(*),'without_items',count(*) FILTER(WHERE itens IS NULL),'without_payments',count(*) FILTER(WHERE pagamentos IS NULL),"
    out += "'compared',count(diferenca),'over_one_cent',count(*) FILTER(WHERE abs(diferenca)>0.01),'positive',count(*) FILTER(WHERE diferenca>0.01),'negative',count(*) FILTER(WHERE diferenca < -0.01),"
    out += "'min_delta',min(diferenca)::text,'max_delta',max(diferenca)::text) FROM ("+reconciliation('gold')+') rec;\n'
    out += "SELECT json_build_object('divergent_status',order_status,'orders',count(*)) FROM ("+reconciliation('gold')+") rec WHERE abs(diferenca)>0.01 GROUP BY order_status ORDER BY order_status;\n"
    return out


def catalog():
    names = ','.join(s.literal(n) for n in SPECS)
    return f"""SELECT json_build_object('columns',json_agg(json_build_object('table',c.relname,'name',a.attname,'type',format_type(a.atttypid,a.atttypmod),'not_null',a.attnotnull) ORDER BY c.relname,a.attnum))
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='gold' AND c.relname IN ({names}) AND a.attnum>0 AND NOT a.attisdropped;
SELECT json_build_object('constraints',json_agg(json_build_object('table',c.relname,'name',k.conname,'kind',k.contype,'target',CASE WHEN k.contype='f' THEN k.confrelid::regclass::text ELSE NULL END,'validated',k.convalidated,'definition',pg_get_constraintdef(k.oid)) ORDER BY c.relname,k.conname))
FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='gold' AND c.relname IN ({names});
"""


def upstream_catalog():
    dimensions = ','.join(s.literal(n) for n in d.SPECS)
    return f"""SELECT json_build_object('upstream_tables',json_agg(json_build_object('schema',n.nspname,'name',c.relname,'oid',c.oid::bigint,'filenode',c.relfilenode::bigint) ORDER BY n.nspname,c.relname))
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND (n.nspname='silver' OR (n.nspname='gold' AND c.relname IN ({dimensions})));
SELECT json_build_object('dimension_columns',json_agg(json_build_object('table',c.relname,'name',a.attname,'type',format_type(a.atttypid,a.atttypmod),'not_null',a.attnotnull) ORDER BY c.relname,a.attnum))
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid WHERE n.nspname='gold' AND c.relname IN ({dimensions}) AND a.attnum>0 AND NOT a.attisdropped;
SELECT json_build_object('dimension_constraints',json_agg(json_build_object('table',c.relname,'kind',k.contype,'definition',pg_get_constraintdef(k.oid)) ORDER BY c.relname,k.contype,k.conname))
FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='gold' AND c.relname IN ({dimensions});
"""


def preflight_observations():
    out = "SELECT json_build_object('database',current_database(),'version',current_setting('server_version'),'isolated',true);\n"
    for name, (entity, pk) in SPECS.items():
        keys = ','.join(s.ident(n) for n in pk)
        out += f"SELECT json_build_object('fact',{s.literal(name)},'silver_rows',count(*),'source_distinct',(SELECT count(*) FROM (SELECT {keys} FROM {s.table(entity)} GROUP BY {keys}) q)) FROM {s.table(entity)};\n"
    return out


def read_sql(work, label, statements):
    return d.run_sql(work,label,statements)


def locked_prefix():
    return d.prefix()+d.locks()+'LOCK TABLE '+','.join('gold.'+s.ident(n) for n in d.SPECS)+' IN SHARE MODE;\n'


def dimension_fingerprints(rows):
    return {x['dimension']:x['fingerprint'] for x in rows if 'dimension' in x and 'fingerprint' in x}


def check_dim_reference(rows, approved, approved_catalog):
    actual=dimension_fingerprints(rows)
    if set(actual)!=set(d.SPECS) or actual!=dimension_fingerprints(approved['after']):
        raise s.SilverError('Dimensões ou SKs diferem da versão aprovada.')
    for label,expected in [('dimension_columns',approved_catalog[1]['columns']),
                            ('dimension_constraints',approved_catalog[2]['constraints'])]:
        present=next((row[label] for row in rows if label in row),None)
        if present!=expected:
            raise s.SilverError('DDL real das dimensões difere do catálogo aprovado: '+label)


def run(output, mode='run'):
    output.mkdir(parents=True,exist_ok=False)
    report=dict(status='started',mode=mode,started_utc=datetime.now(timezone.utc).isoformat(),errors=[],runs={})
    try:
        if os.environ.get('PGDATABASE')!='inteligencia_receita_db' or s.environment_status()['blockers']:
            raise s.SilverError('Conexão protegida indisponível para o banco do projeto.')
        approved=json.loads((d.EVIDENCE/'integracao/verify/resultado.json').read_text(encoding='utf-8'))
        dim_approved=json.loads((DIM_EVIDENCE/'resultado.json').read_text(encoding='utf-8'))
        dim_catalog=json.loads((DIM_EVIDENCE/'catalogo.json').read_text(encoding='utf-8'))
        if approved['status']!='verified_readonly' or dim_approved['status']!='completed_verified':
            raise s.SilverError('Evidências de entrada incompatíveis.')
        for st in approved['sources'].values():
            if s.sha256(s.ROOT/'data/bronze'/st['file'])!=st['sha256']:
                raise s.SilverError('Bronze difere da versão estática aprovada.')
        artifacts={'003_fatos.sql':ddl(),'004_carga_fatos.sql':load()}
        for name,generated in artifacts.items():
            if (s.ROOT/'sql/gold'/name).read_text(encoding='utf-8')!=generated:
                raise s.SilverError('DDL ou carga dos fatos difere do gerador revisado.')
        if (s.ROOT/'sql/validacoes/gold_fatos.sql').read_text(encoding='utf-8')!=validation()+observations():
            raise s.SilverError('Validações dos fatos diferem do gerador revisado.')
        with tempfile.TemporaryDirectory(prefix='olist_fatos_') as folder:
            work=Path(folder)
            compatible=guard()+source_checks()+s.validation_sql(approved['sources'])+d.validation()
            report['preflight']=read_sql(work,'preflight',d.prefix(True)+compatible+preflight_observations()+d.observations()+upstream_catalog()+'ROLLBACK;\n')
            check_dim_reference(report['preflight'],dim_approved,dim_catalog)
            # Evidência antes de qualquer DDL persistida mesmo se a carga falhar.
            (output/'preflight.json').write_text(json.dumps(report['preflight'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print('Banco, Silver, dimensões e granularidades validados antes do DDL.',flush=True)
            if mode=='inspect':
                report['status']='inspected_readonly'
            else:
                for stage,rollback in [('first',False),('second',False),('rollback',True)]:
                    statements=locked_prefix()+guard()+source_checks()+d.validation()
                    statements+=(s.ROOT/'sql/gold/003_fatos.sql').read_text(encoding='utf-8')
                    statements+=(s.ROOT/'sql/gold/004_carga_fatos.sql').read_text(encoding='utf-8')
                    statements+=guard()+validation()+constraint_tests()+observations()
                    if rollback:
                        statements+="DO $canary$ BEGIN UPDATE gold.fato_pedidos SET order_status='__rollback_probe__' WHERE order_id=(SELECT min(order_id) FROM gold.fato_pedidos); IF NOT FOUND THEN RAISE EXCEPTION 'Canário ausente'; END IF; END $canary$;\nSELECT 1/0;\n"
                    statements+='COMMIT;\n'
                    try:
                        rows=read_sql(work,stage,statements)
                        if rollback:
                            raise s.SilverError('Falha deliberada não ocorreu.')
                        report['runs'][stage]=dict(status='committed',results=rows)
                    except s.SilverError as exc:
                        if not rollback or 'SQLSTATE 22012' not in str(exc):
                            raise
                        report['runs'][stage]=dict(status='expected_failure',sqlstate='22012')
                    (output/(stage+'.json')).write_text(json.dumps(report['runs'][stage],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    print('Etapa '+stage+': '+report['runs'][stage]['status'],flush=True)
                report['after']=read_sql(work,'verify',d.prefix(True)+compatible+validation()+observations()+d.observations()+upstream_catalog()+catalog()+s.observation_sql()+'ROLLBACK;\n')
                report['idempotence']=report['runs']['first']['results']==report['runs']['second']['results']
                count=len(report['runs']['second']['results'])
                report['rollback_confirmed']=report['after'][:count]==report['runs']['second']['results']
                report['dimensions_preserved']=dimension_fingerprints(report['after'])==dimension_fingerprints(report['preflight'])
                before_catalog=[x for x in report['preflight'] if 'upstream_tables' in x or 'dimension_columns' in x or 'dimension_constraints' in x]
                after_catalog=[x for x in report['after'] if 'upstream_tables' in x or 'dimension_columns' in x or 'dimension_constraints' in x]
                report['upstream_catalog_preserved']=before_catalog==after_catalog
                if not all(report[k] for k in ['idempotence','rollback_confirmed','dimensions_preserved','upstream_catalog_preserved']):
                    raise s.SilverError('Reexecução, rollback ou preservação divergente.')
                report['silver_preserved']=True
                report['status']='completed_verified'
        report['bronze_preserved']=all(s.sha256(s.ROOT/'data/bronze'/st['file'])==st['sha256'] for st in approved['sources'].values())
        if not report['bronze_preserved']:
            raise s.SilverError('Bronze mudou por processo externo; verificar evidências.')
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
    parser.add_argument('--output',type=Path,default=s.ROOT/'docs/qualidade/etapa4_gold_fatos'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    args=parser.parse_args()
    result=run(args.output.resolve(),args.mode)
    print(json.dumps(dict(status=result['status'],errors=result['errors'],output=str(args.output)),ensure_ascii=True))
    raise SystemExit(0 if not result['errors'] else 1)


if __name__=='__main__':
    main()
