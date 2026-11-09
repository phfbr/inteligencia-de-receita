"""Etapa 5: SELECTs reproduzíveis, reconciliação exata e evidências sem escrita no banco."""
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import silver as s
import gold_dimensoes as d
import gold_fatos as f

SQLDIR = s.ROOT / 'sql/validacoes/analitica'


def base(layer, kind):
    gold = layer == 'gold'
    names = {'pedidos': ('orders', 'fato_pedidos'), 'itens': ('items', 'fato_itens_pedido'), 'pagamentos': ('payments', 'fato_pagamentos')}
    entity, fact = names[kind]
    table = 'gold.' + fact if gold else s.table(entity)
    extra = ''
    if gold:
        joins = ' LEFT JOIN gold.dim_calendario dt ON dt.data_sk=x.data_compra_sk LEFT JOIN gold.dim_localizacao l ON l.localizacao_sk=x.localizacao_sk'
        day = 'dt.dia'
        status = 'x.order_status'
        geo = 'l.customer_state uf,l.customer_city cidade,l.membro_tipo localizacao_tipo'
    else:
        joins = '' if kind == 'pedidos' else ' LEFT JOIN ' + s.table('orders') + ' o ON o.order_id=x.order_id'
        alias = 'x' if kind == 'pedidos' else 'o'
        joins += ' LEFT JOIN ' + s.table('customers') + f' c ON c.customer_id={alias}.customer_id'
        day = alias + '.order_purchase_timestamp::date'
        status = alias + '.order_status'
        complete = 'c.customer_zip_code_prefix IS NOT NULL AND c.customer_city IS NOT NULL AND c.customer_state IS NOT NULL'
        geo = f"CASE WHEN {complete} THEN c.customer_state END uf,CASE WHEN {complete} THEN c.customer_city END cidade,CASE WHEN {alias}.customer_id IS NULL THEN 'nao_informado' WHEN c.customer_id IS NULL THEN 'referencia_nao_encontrada' WHEN NOT ({complete}) THEN 'nao_informado' ELSE 'regular' END localizacao_tipo"
    if kind == 'pedidos':
        if gold:
            joins += ' LEFT JOIN gold.dim_clientes c ON c.cliente_sk=x.cliente_sk'
        extra = ',c.customer_unique_id'
    if kind == 'itens':
        if gold:
            joins += ' LEFT JOIN gold.dim_produtos p ON p.produto_sk=x.produto_sk LEFT JOIN gold.dim_vendedores v ON v.vendedor_sk=x.vendedor_sk'
            english = 'p.product_category_name_english'
        else:
            joins += ' LEFT JOIN ' + s.table('products') + ' p ON p.product_id=x.product_id LEFT JOIN ' + s.table('sellers') + ' v ON v.seller_id=x.seller_id LEFT JOIN ' + s.table('translation') + ' t ON t.product_category_name=p.product_category_name'
            english = 't.product_category_name_english'
        extra = f',x.order_item_id,x.price,x.freight_value,p.product_id,p.product_category_name,{english} product_category_name_english,v.seller_id'
    if kind == 'pagamentos':
        if gold:
            joins += ' LEFT JOIN gold.dim_forma_pagamento m ON m.forma_pagamento_sk=x.forma_pagamento_sk'
        extra = ',x.payment_sequential,x.payment_value,' + ('m.payment_type' if gold else 'x.payment_type') + ' payment_type'
    return f'SELECT x.order_id,{status} order_status,{day} dia_compra,date_trunc(\'month\',{day})::date mes,{geo}{extra} FROM {table} x{joins}'


def scoped(query):
    return f"WITH b AS ({query}), a AS (SELECT 'geral'::text escopo,b.* FROM b UNION ALL SELECT 'delivered',b.* FROM b WHERE order_status='delivered') "


def aggregate(layer, kind, groups):
    measure = 'count(*) linhas,count(DISTINCT order_id) pedidos'
    if kind == 'itens':
        measure += ',sum(price) price,sum(freight_value) freight_value'
    if kind == 'pagamentos':
        measure += ',sum(payment_value) payment_value'
    cols = ['escopo'] + groups
    return scoped(base(layer, kind)) + 'SELECT ' + ','.join(cols) + ',' + measure + ' FROM a GROUP BY ' + ','.join(cols)


def customers(layer):
    return 'WITH b AS (' + base(layer, 'pedidos') + ") SELECT customer_unique_id,count(DISTINCT order_id) pedidos,count(DISTINCT order_id) FILTER(WHERE order_status='delivered') delivered,count(DISTINCT dia_compra) FILTER(WHERE order_status='delivered') dias_delivered,min(dia_compra) primeira_compra,max(dia_compra) ultima_compra FROM b WHERE customer_unique_id IS NOT NULL GROUP BY customer_unique_id"


def recurrence(layer):
    return 'WITH c AS (' + customers(layer) + ") SELECT count(*) identidades_observadas,count(*) FILTER(WHERE pedidos>1) multiplos_pedidos,count(*) FILTER(WHERE delivered>=2) multiplos_delivered,count(*) FILTER(WHERE dias_delivered>=1) denominador,count(*) FILTER(WHERE dias_delivered>=2) numerador,100::numeric*count(*) FILTER(WHERE dias_delivered>=2)/nullif(count(*) FILTER(WHERE dias_delivered>=1),0) percentual_descritivo FROM c"


def rec(layer):
    return scoped('SELECT b.*,r.itens,r.pagamentos,r.preco,r.frete,r.valor,r.diferenca FROM (' + base(layer, 'pedidos') + ') b JOIN (' + f.reconciliation(layer) + ') r USING(order_id)') + "SELECT escopo,CASE WHEN grouping(order_status)=0 THEN 'status' WHEN grouping(mes)=0 THEN 'mes' WHEN grouping(uf)=0 THEN 'uf' ELSE 'geral' END nivel,order_status,mes,uf,count(*) pedidos,count(*) FILTER(WHERE itens IS NULL) sem_itens,count(*) FILTER(WHERE pagamentos IS NULL) sem_pagamentos,count(diferenca) comparaveis,count(*) FILTER(WHERE abs(diferenca)>0.01) divergencias,count(*) FILTER(WHERE diferenca>0.01) positivas,count(*) FILTER(WHERE diferenca < -0.01) negativas,sum(preco) price,sum(frete) freight_value,sum(valor) payment_value FROM a GROUP BY escopo,GROUPING SETS((),(order_status),(mes),(uf))"


def analyses(layer):
    result = {}
    for kind, levels in {
        'pedidos': {'resumo': [], 'status': ['order_status'], 'mensal': ['mes'], 'uf': ['localizacao_tipo','uf'], 'cidade': ['localizacao_tipo','uf','cidade']},
        'itens': {'resumo': [], 'mensal': ['mes'], 'produto': ['product_id','product_category_name','product_category_name_english'], 'categoria': ['product_category_name','product_category_name_english'], 'vendedor': ['seller_id'], 'uf': ['localizacao_tipo','uf'], 'cidade': ['localizacao_tipo','uf','cidade']},
        'pagamentos': {'resumo': [], 'mensal': ['mes','payment_type','order_status'], 'forma_status': ['payment_type','order_status'], 'uf': ['localizacao_tipo','uf'], 'cidade': ['localizacao_tipo','uf','cidade']},
    }.items():
        for level, groups in levels.items():
            result[kind + '_' + level] = aggregate(layer, kind, groups)
    result['clientes_pedidos'] = customers(layer)
    result['clientes_recompra'] = recurrence(layer)
    result['reconciliacao_pedido_niveis'] = rec(layer)
    return result


def cardinalities():
    queries = []
    for fact, (_, pk) in f.SPECS.items():
        joins = ' '.join(f'LEFT JOIN gold.{dim} d{i} ON d{i}.{key}=x.{col}' for i,(col,dim,key) in enumerate(f.fks(fact)))
        missing = ' OR '.join(f'd{i}.{key} IS NULL' for i,(_,_,key) in enumerate(f.fks(fact)))
        keycols = ','.join('x.' + key for key in pk)
        queries.append(f"SELECT '{fact}' fato,(SELECT count(*) FROM gold.{fact}) origem,count(*) apos_joins,count(DISTINCT ({keycols})) graos,count(*) FILTER(WHERE {missing}) fk_ausente FROM gold.{fact} x {joins}")
    return ' UNION ALL '.join(queries)


def temporal():
    parts = []
    for fact in f.SPECS:
        roles = f.ORDER_DATES if fact == 'fato_pedidos' else {'order_purchase_timestamp':'data_compra_sk', **({'shipping_limit_date':'data_limite_envio_sk'} if fact=='fato_itens_pedido' else {})}
        for ts, sk in roles.items():
            parts.append(f"SELECT '{fact}' fato,'{ts}' papel,count(*) linhas,count(*) FILTER(WHERE x.{ts} IS NULL) ausentes,count(*) FILTER(WHERE x.{ts} IS NULL AND x.{sk}<>-1 OR x.{ts} IS NOT NULL AND (c.dia IS DISTINCT FROM x.{ts}::date)) divergencias,min(x.{ts}) minimo,max(x.{ts}) maximo FROM gold.{fact} x LEFT JOIN gold.dim_calendario c ON c.data_sk=x.{sk}")
    return ' UNION ALL '.join(parts)


def queries():
    gold, source = analyses('gold'), analyses('silver')
    gold['validacao_silver_gold'] = ' UNION ALL '.join(f"SELECT '{name}' analise,count(*) diferencas FROM ((({query}) EXCEPT ALL ({source[name]})) UNION ALL (({source[name]}) EXCEPT ALL ({query}))) diferencas" for name,query in gold.items())
    gold['validacao_cardinalidades'] = cardinalities()
    gold['validacao_datas'] = temporal()
    gold['qualidade_denominadores'] = "SELECT count(*) pedidos,count(*) FILTER(WHERE cliente_sk IN(-1,-2)) identidade_tecnica,count(*) FILTER(WHERE localizacao_sk IN(-1,-2)) localizacao_tecnica,count(*) FILTER(WHERE order_purchase_timestamp IS NULL) compra_ausente,count(*) FILTER(WHERE order_status='delivered' AND order_purchase_timestamp IS NULL) delivered_compra_ausente,count(DISTINCT cliente_sk) FILTER(WHERE cliente_sk>0) identidades_regulares,(SELECT count(*) FROM gold.dim_clientes WHERE membro_tipo='regular') identidades_dimensao FROM gold.fato_pedidos"
    return gold


def safe(query):
    if not re.match(r'^(SELECT|WITH)\b', query, re.I) or ';' in query or re.search(r'\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|COPY|CALL|DO|INTO)\b', query, re.I):
        raise ValueError('Consulta fora do contrato somente leitura')


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def run_sql(path):
    env = os.environ.copy()
    env.update(PGCONNECT_TIMEOUT='5', PGCLIENTENCODING='UTF8', PSQLRC=os.devnull)
    command = [str(s.psql_path()), '-X','-w','-q','-A','-t','--set=ON_ERROR_STOP=1','--set=VERBOSITY=sqlstate','--file',str(path)]
    p = subprocess.run(command, env=env, capture_output=True, text=True, encoding='utf-8', timeout=1800)
    if p.returncode:
        codes = sorted(set(re.findall(r':\s+([0-9A-Z]{5})(?=\s|$)', p.stderr)))
        raise RuntimeError(f'psql exit={p.returncode}; SQLSTATE={codes}; detalhes de conexão omitidos')
    return [json.loads(line, parse_float=Decimal) for line in p.stdout.splitlines() if line.lstrip().startswith('{')]


def snapshot():
    return f.observations() + d.observations() + f.catalog() + f.upstream_catalog() + ''.join("SELECT json_build_object('silver_table',"+s.literal(entity)+",'fingerprint',encode(sha256(convert_to(string_agg(encode(sha256(convert_to(row_to_json(x)::text,'UTF8')),'hex'),'' ORDER BY _source_row),'UTF8')),'hex')) FROM "+s.table(entity)+" x;\n" for entity in s.TABLES)


def checks(results):
    tests = []
    def check(name, condition):
        tests.append({'teste': name, 'ok': bool(condition)})
    check('reconciliacao_exata_20_analises', all(r['diferencas']==0 for r in results['validacao_silver_gold']))
    check('joins_dimensionais_sem_multiplicacao', all(r['origem']==r['apos_joins']==r['graos'] and r['fk_ausente']==0 for r in results['validacao_cardinalidades']))
    check('todos_papeis_temporais', all(r['divergencias']==0 for r in results['validacao_datas']))
    for kind, measures, levels in [('pedidos', ['linhas'], ['status','mensal','uf','cidade']),('itens',['linhas','price','freight_value'],['mensal','produto','categoria','vendedor','uf','cidade']),('pagamentos',['linhas','payment_value'],['mensal','forma_status','uf','cidade'])]:
        for total in results[kind+'_resumo']:
            for level in levels:
                rows = [r for r in results[kind+'_'+level] if r['escopo']==total['escopo']]
                for measure in measures:
                    check(f'{kind}_{level}_{total["escopo"]}_{measure}', sum((r[measure] or 0 for r in rows),Decimal(0)) == total[measure])
    clients = results['clientes_recompra'][0]
    details = results['clientes_pedidos']
    check('RN07_numerador', clients['numerador']==sum(r['dias_delivered']>=2 for r in details))
    check('RN07_denominador', clients['denominador']==sum(r['dias_delivered']>=1 for r in details))
    check('RN07_subconjunto', 0<=clients['numerador']<=clients['denominador']<=clients['identidades_observadas'])
    check('clientes_cobertura', sum(r['pedidos'] for r in details)==results['qualidade_denominadores'][0]['pedidos']-results['qualidade_denominadores'][0]['identidade_tecnica'])
    for total in [r for r in results['reconciliacao_pedido_niveis'] if r['nivel']=='geral']:
        for level in ['status','mes','uf']:
            rows=[r for r in results['reconciliacao_pedido_niveis'] if r['nivel']==level and r['escopo']==total['escopo']]
            for measure in ['pedidos','sem_itens','sem_pagamentos','comparaveis','divergencias','positivas','negativas','price','freight_value','payment_value']:
                check(f'reconciliacao_{level}_{total["escopo"]}_{measure}',sum((r[measure] or 0 for r in rows),Decimal(0))==total[measure])
    return tests


def main():
    SQLDIR.mkdir(parents=True, exist_ok=True)
    catalog = queries()
    for i,(name,query) in enumerate(catalog.items(),1):
        safe(query)
        (SQLDIR/f'{i:02d}_{name}.sql').write_text('-- Etapa 5. Leitura; escopos geral e delivered se sobrepõem.\n'+query+';\n',encoding='utf-8')
    if '--prepare' in sys.argv:
        print(f'{len(catalog)} consultas preparadas; banco não acessado.')
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    work=s.ROOT/'docs/qualidade/etapa5_validacao_analitica'/stamp
    work.mkdir(parents=True)
    bronze={str(p.relative_to(s.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (s.ROOT/'data/bronze').glob('*.csv')}
    identity="SELECT json_build_object('database',current_database(),'version',current_setting('server_version'),'read_only',current_setting('transaction_read_only'),'isolation',current_setting('transaction_isolation'),'marker',shobj_description(oid,'pg_database')) FROM pg_database WHERE datname=current_database();\n"
    try:
        pre=work/'00_preflight.sql'
        pre.write_text(d.prefix(True)+identity+'ROLLBACK;\n',encoding='utf-8')
        conn=run_sql(pre)
        dump(work/'conexao.json',conn)
        if len(conn)!=1 or conn[0]['database']!='inteligencia_receita_db' or conn[0]['read_only']!='on' or conn[0]['marker']!='inteligencia_receita:exclusive:v1':
            raise RuntimeError('Destino ou contrato somente leitura não confirmado')
        statements=d.prefix(True)+identity+"SELECT json_build_object('marco','antes');\n"+snapshot()
        for name,query in catalog.items():
            statements+=f"SELECT json_build_object('analise','{name}','rows',coalesce(json_agg(row_to_json(q)),'[]'::json)) FROM ({query}) q;\n"
        statements+="SELECT json_build_object('marco','depois');\n"+snapshot()+'ROLLBACK;\n'
        execution=work/'execucao.sql'
        execution.write_text(statements,encoding='utf-8')
        records=run_sql(execution)
        before_index=records.index({'marco':'antes'})
        after_index=records.index({'marco':'depois'})
        first_analysis=next(i for i,r in enumerate(records) if 'analise' in r)
        before=records[before_index+1:first_analysis]
        after=records[after_index+1:]
        results={r['analise']:r['rows'] for r in records if 'analise' in r}
        tests=checks(results)
        tests.append({'teste':'conteudo_estrutura_antes_depois','ok':before==after})
        tests.append({'teste':'bronze_sha256_preservado','ok':bronze=={name:hashlib.sha256((s.ROOT/name).read_bytes()).hexdigest() for name in bronze}})
        approved=json.loads((s.ROOT/'docs/qualidade/etapa4_gold_fatos/20261108T035602100511Z/resultado.json').read_text(encoding='utf-8'))
        def hashes(rows):
            return {r.get('fact',r.get('dimension')):r['fingerprint'] for r in rows if 'fingerprint' in r and ('fact' in r or 'dimension' in r)}
        tests.append({'teste':'nove_objetos_gold_iguais_evidencia_4C','ok':hashes(before)==hashes(approved['after'])})
        for name,rows in results.items():
            dump(work/(name+'.json'), rows)
            if rows:
                with (work/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as out:
                    writer=csv.DictWriter(out,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
        dump(work/'snapshots.json',{'antes':before,'depois':after,'bronze':bronze})
        dump(work/'testes.json',tests)
        summary={'status':'verificado_somente_leitura' if all(t['ok'] for t in tests) else 'falha_validacao','consultas':len(catalog),'testes':len(tests),'falhas':[t for t in tests if not t['ok']],'conexao':conn,'inicio_utc':stamp,'fim_utc':datetime.now(timezone.utc).isoformat()}
        dump(work/'resultado.json',summary)
        print(json.dumps({'evidencias':str(work),'resumo':summary},ensure_ascii=False))
    except Exception as exc:
        dump(work/'erro.json',{'tipo':type(exc).__name__,'erro':str(exc)})
        print(f'Bloqueio: {exc}');raise SystemExit(1)


if __name__=='__main__':
    main()
