"""Etapa 6C: execução somente leitura; reutiliza transporte protegido da Etapa 5."""
import sys
import json
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import validacao_analitica as v

ROOT = v.s.ROOT
SQL = ROOT / 'sql/validacoes/powerbi'
OUT = ROOT / 'docs/qualidade/etapa6c_evidencias'

def queries():
    bases = {}
    for alias, fact in [('p','fato_pedidos'),('i','fato_itens_pedido'),('g','fato_pagamentos')]:
        bases[alias] = f"SELECT x.*,c.dia,c.mes FROM gold.{fact} x LEFT JOIN gold.dim_calendario c ON c.data_sk=x.data_compra_sk LEFT JOIN gold.dim_localizacao l ON l.localizacao_sk=x.localizacao_sk WHERE c.ano=2017 AND l.customer_state='SP'"
    prefix = 'WITH ' + ','.join(f'{k} AS ({q})' for k,q in bases.items()) + ' '
    q = {}
    q['01_kpis'] = prefix + "SELECT (SELECT count(DISTINCT order_id) FROM p) pedidos,(SELECT count(DISTINCT order_id) FROM p WHERE order_status='delivered') delivered,(SELECT sum(price) FROM i) price,(SELECT sum(freight_value) FROM i) freight_value,(SELECT sum(payment_value) FROM g) payment_value"
    statuses = "(VALUES ('approved'),('canceled'),('created'),('delivered'),('invoiced'),('processing'),('shipped'),('unavailable'))"
    q['02_status'] = prefix + f", dominio AS (SELECT column1 status FROM {statuses} s UNION SELECT order_status FROM p), a AS (SELECT order_status,count(DISTINCT order_id) pedidos FROM p GROUP BY order_status) SELECT d.status,coalesce(a.pedidos,0) pedidos,coalesce(a.pedidos,0)*100::numeric/nullif((SELECT count(DISTINCT order_id) FROM p),0) percentual,(SELECT count(DISTINCT order_id) FROM p) denominador FROM dominio d LEFT JOIN a ON a.order_status IS NOT DISTINCT FROM d.status ORDER BY d.status NULLS FIRST"
    q['03_meses'] = prefix + ", a AS (SELECT date_trunc('month',dia)::date mes,count(*) itens,sum(price) price,sum(freight_value) freight_value FROM i GROUP BY 1) SELECT make_date(2017,n,1) mes,coalesce(a.itens,0) itens,a.price,a.freight_value FROM generate_series(1,12) n LEFT JOIN a ON a.mes=make_date(2017,n,1) ORDER BY 1"
    q['04_categorias'] = prefix + ", a AS (SELECT d.membro_tipo,d.product_category_name,count(*) itens,sum(i.price) price,sum(i.freight_value) freight_value FROM i LEFT JOIN gold.dim_produtos d ON d.produto_sk=i.produto_sk GROUP BY 1,2) SELECT rank() OVER(ORDER BY price DESC NULLS LAST) posicao,a.* FROM a ORDER BY price DESC NULLS LAST,product_category_name NULLS FIRST,membro_tipo"
    q['05_vendedores'] = prefix + ", a AS (SELECT i.vendedor_sk,d.seller_id,d.membro_tipo,'Vendedor '||i.vendedor_sk rotulo,count(*) itens,sum(i.price) price,sum(i.freight_value) freight_value FROM i LEFT JOIN gold.dim_vendedores d ON d.vendedor_sk=i.vendedor_sk GROUP BY 1,2,3) SELECT rank() OVER(ORDER BY price DESC NULLS LAST) posicao,a.* FROM a ORDER BY price DESC NULLS LAST,vendedor_sk"
    q['06_metodos'] = prefix + ", a AS (SELECT forma_pagamento_sk,count(*) registros,count(DISTINCT order_id) pedidos,sum(payment_value) payment_value FROM g GROUP BY 1) SELECT d.forma_pagamento_sk,d.payment_type,d.membro_tipo,coalesce(a.registros,0) registros,coalesce(a.pedidos,0) pedidos,a.payment_value FROM gold.dim_forma_pagamento d LEFT JOIN a USING(forma_pagamento_sk) ORDER BY d.forma_pagamento_sk"
    rec = prefix + ", ia AS (SELECT order_id,count(*) itens,sum(price) price,sum(freight_value) freight_value FROM i GROUP BY 1), ga AS (SELECT order_id,count(*) pagamentos,sum(payment_value) payment_value FROM g GROUP BY 1), r AS (SELECT p.order_id,p.order_status,p.mes,ia.itens,ga.pagamentos,ia.price,ia.freight_value,ga.payment_value,ga.payment_value-ia.price-ia.freight_value diferenca FROM p LEFT JOIN ia USING(order_id) LEFT JOIN ga USING(order_id)) "
    q['07_reconciliacao'] = rec + "SELECT CASE WHEN grouping(order_status)=0 THEN 'status' WHEN grouping(mes)=0 THEN 'mes' ELSE 'total' END nivel,order_status,mes,count(*) pedidos,count(*) FILTER(WHERE itens IS NULL) sem_itens,count(*) FILTER(WHERE pagamentos IS NULL) sem_pagamentos,count(diferenca) comparaveis,count(*) FILTER(WHERE diferenca<>0) diferencas_nao_zero,count(*) FILTER(WHERE abs(diferenca)>0.01) divergencias,sum(price) price,sum(freight_value) freight_value,sum(payment_value) payment_value,sum(diferenca) diferenca_comparaveis FROM r GROUP BY GROUPING SETS((),(order_status),(mes)) ORDER BY 1,2,3"
    q['08_diferencas_pedido'] = rec + "SELECT * FROM r WHERE diferenca IS NULL OR diferenca<>0 ORDER BY order_id"
    parts=[]
    for alias,fact in [('p','fato_pedidos'),('i','fato_itens_pedido'),('g','fato_pagamentos')]:
        measures = ',sum(price) price,sum(freight_value) freight_value,NULL::numeric payment_value' if alias=='i' else ',NULL::numeric price,NULL::numeric freight_value,'+('sum(payment_value)' if alias=='g' else 'NULL::numeric')+' payment_value'
        parts.append(f"SELECT '{fact}' fato,count(*) linhas,count(DISTINCT order_id) pedidos{measures} FROM {alias}")
    q['09_fatos'] = prefix + ' UNION ALL '.join(parts)
    audits=[]
    for alias,fact in [('i','fato_itens_pedido'),('g','fato_pagamentos')]:
        audits.append(f"SELECT '{fact}' fato,(SELECT count(*) FROM {alias} x LEFT JOIN gold.fato_pedidos z USING(order_id) WHERE z.order_id IS NULL OR (x.cliente_sk,x.localizacao_sk,x.data_compra_sk,x.order_status,x.order_purchase_timestamp) IS DISTINCT FROM (z.cliente_sk,z.localizacao_sk,z.data_compra_sk,z.order_status,z.order_purchase_timestamp)) contexto_divergente,(SELECT count(*) FROM ((SELECT order_id FROM {alias}) EXCEPT (SELECT x.order_id FROM gold.{fact} x JOIN p USING(order_id))) a) fora_escopo,(SELECT count(*) FROM ((SELECT x.order_id FROM gold.{fact} x JOIN p USING(order_id)) EXCEPT (SELECT order_id FROM {alias})) a) faltando_escopo")
    q['10_contexto'] = prefix + ' UNION ALL '.join(audits)
    for kind in ['pedidos','itens','pagamentos']:
        q['11_geral_'+kind]=v.aggregate('gold',kind,[])
    q['12_cardinalidades']=v.cardinalities()
    q['13_datas']=v.temporal()
    return q

def main():
    SQL.mkdir(parents=True,exist_ok=True)
    catalog=queries()
    for name,query in catalog.items():
        v.safe(query)
        (SQL/(name+'.sql')).write_text('-- Etapa 6C. Compra 2017; UF do pedido SP; todos os status. Executar READ ONLY.\n'+query+';\n',encoding='utf-8')
    if '--prepare' in sys.argv: return
    OUT.mkdir(parents=True,exist_ok=True)
    identity="SELECT json_build_object('database',current_database(),'usuario',current_user,'sessao',session_user,'proprietario',pg_get_userbyid(datdba),'marker',shobj_description(oid,'pg_database'),'read_only',current_setting('transaction_read_only'),'isolation',current_setting('transaction_isolation'),'version',current_setting('server_version'),'instante',clock_timestamp()) FROM pg_database WHERE datname=current_database();\n"
    pre=OUT/'00_preflight.sql'
    pre.write_text(v.d.prefix(True)+identity+'ROLLBACK;\n',encoding='utf-8')
    conn=v.run_sql(pre)
    v.dump(OUT/'conexao.json',conn)
    c=conn[0]
    assert c['database']=='inteligencia_receita_db' and c['marker']=='inteligencia_receita:exclusive:v1' and c['usuario']==c['proprietario']==c['sessao'] and c['read_only']=='on'
    script=v.d.prefix(True)+identity+"SELECT json_build_object('marco','antes');\n"+v.f.observations()+v.d.observations()
    for name,query in catalog.items():
        script+=f"SELECT json_build_object('analise','{name}','rows',coalesce(json_agg(row_to_json(q)),'[]'::json)) FROM ({query}) q;\n"
    script+="SELECT json_build_object('marco','depois');\n"+v.f.observations()+v.d.observations()+'ROLLBACK;\n'
    path=OUT/'execucao.sql';path.write_text(script,encoding='utf-8')
    records=v.run_sql(path)
    v.dump(OUT/'execucao.json',records)
    results={r['analise']:r['rows'] for r in records if 'analise' in r}
    for name,rows in results.items(): v.dump(OUT/(name+'.json'),rows)
    tests=[]
    def check(name,a,b): tests.append(dict(teste=name,atual=a,esperado=b,ok=a==b))
    k=results['01_kpis'][0]
    check('status_pedidos',sum(r['pedidos'] for r in results['02_status']),k['pedidos'])
    for name,fields in [('03_meses',['price','freight_value']),('04_categorias',['price','freight_value']),('05_vendedores',['price','freight_value']),('06_metodos',['payment_value'])]:
        for field in fields: check(name+'_'+field,sum((r[field] or Decimal(0) for r in results[name]),Decimal(0)),k[field])
    for kind in ['pedidos','itens','pagamentos']:
        old=json.loads((ROOT/'docs/qualidade/etapa5_validacao_analitica/20261108T042110748288Z'/f'{kind}_resumo.json').read_text(encoding='utf-8'),parse_float=Decimal)
        for actual in results['11_geral_'+kind]:
            ref=next(r for r in old if r['escopo']==actual['escopo'])
            for field,val in actual.items(): check(f'geral_{kind}_{actual["escopo"]}_{field}',str(val),str(ref[field]))
    total=next(r for r in results['07_reconciliacao'] if r['nivel']=='total')
    for level in ['status','mes']:
        for field in ['pedidos','sem_itens','sem_pagamentos','comparaveis','divergencias','price','freight_value','payment_value','diferenca_comparaveis']:
            check('pedido_'+level+'_'+field,sum((r[field] or 0 for r in results['07_reconciliacao'] if r['nivel']==level),Decimal(0)),total[field])
    for field in ['pedidos','price','freight_value','payment_value']: check('independente_pedido_'+field,total[field],k[field])
    for r in results['10_contexto']:
        for field in ['contexto_divergente','fora_escopo','faltando_escopo']: check(r['fato']+'_'+field,r[field],0)
    for r in results['12_cardinalidades']:
        check(r['fato']+'_join',r['apos_joins'],r['origem']);check(r['fato']+'_grao',r['graos'],r['origem']);check(r['fato']+'_fk',r['fk_ausente'],0)
    for r in results['13_datas']:check(r['fato']+'_'+r['papel'],r['divergencias'],0)
    start=records.index({'marco':'antes'})+1;end=next(n for n,r in enumerate(records) if 'analise' in r)
    after=records.index({'marco':'depois'})+1
    check('gold_antes_depois',records[start:end],records[after:])
    v.dump(OUT/'testes.json',tests)
    v.dump(OUT/'resultado.json',dict(fim_utc=datetime.now(timezone.utc).isoformat(),consultas=len(catalog),testes=len(tests),falhas=[t for t in tests if not t['ok']],sql_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SQL.glob('*.sql')}))
    print(json.dumps(dict(kpis=k,reconciliacao=total,testes=len(tests),falhas=[t for t in tests if not t['ok']]),default=str))

if __name__=='__main__':main()
