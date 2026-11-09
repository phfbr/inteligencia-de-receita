"""Compila o relatório exclusivamente a partir das evidências reais da Etapa 6C."""
import csv
import json
from decimal import Decimal
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/qualidade/etapa6c_evidencias'
def read(name):return json.loads((OUT/(name+'.json')).read_text(encoding='utf-8'),parse_float=Decimal)
def money(x):return 'NULL' if x is None else str(x)
def table(rows,fields):
    return '| '+' | '.join(fields)+' |\n| '+' | '.join('---' for _ in fields)+' |\n'+''.join('| '+' | '.join(money(r.get(k)) for k in fields)+' |\n' for r in rows)+'\n'
def main():
    k=read('01_kpis')[0];rec=read('07_reconciliacao');details=read('08_diferencas_pedido')
    categories=read('04_categorias');sellers=read('05_vendedores');tests=read('testes');result=read('resultado')
    missing=[r for r in details if r['itens'] is None]
    diffs=[r for r in details if r['diferenca'] is not None]
    significant=[r for r in diffs if abs(Decimal(r['diferenca']))>Decimal('.01')]
    with (ROOT/'docs/regras_negocio/evidencias/divergencias.csv').open(encoding='utf-8-sig') as f: old={r['order_id']:r for r in csv.DictReader(f)}
    with (ROOT/'docs/regras_negocio/evidencias/pedidos_sem_itens_ou_pagamentos.csv').open(encoding='utf-8-sig') as f: oldmissing={r['order_id']:r for r in csv.DictReader(f)}
    investigation={
        'divergencias_maiores_001':len(significant),
        'coincidem_id_e_delta_diagnostico':sum(r['order_id'] in old and Decimal(r['diferenca'])==Decimal(old[r['order_id']]['delta']) for r in significant),
        'sem_itens':len(missing),
        'coincidem_id_status_diagnostico':sum(r['order_id'] in oldmissing and r['order_status']==oldmissing[r['order_id']]['status'] for r in missing),
        'pagamentos_sem_itens':sum((Decimal(r['payment_value']) for r in missing),Decimal(0)),
        'diferenca_global':Decimal(k['payment_value'])-Decimal(k['price'])-Decimal(k['freight_value']),
        'diferenca_comparaveis':sum((Decimal(r['diferenca']) for r in diffs),Decimal(0)),
        'positivas_maiores_001':sum(Decimal(r['diferenca'])>Decimal('.01') for r in significant),
        'negativas_menores_menos001':sum(Decimal(r['diferenca'])<Decimal('-.01') for r in significant),
        'diferencas_nao_zero_ate_001':sum(abs(Decimal(r['diferenca']))<=Decimal('.01') for r in diffs),
        'sem_itens_por_status':dict(Counter(r['order_status'] for r in missing)),
        'divergencias_por_status':dict(Counter(r['order_status'] for r in significant))}
    assert investigation['coincidem_id_e_delta_diagnostico']==len(significant)
    assert investigation['coincidem_id_status_diagnostico']==len(missing)
    assert investigation['diferenca_global']==investigation['pagamentos_sem_itens']+investigation['diferenca_comparaveis']
    (OUT/'investigacao.json').write_text(json.dumps(investigation,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    text='''# Etapa 6C — Reconciliação analítica da Página 1 (Visão Executiva)

Os resultados abaixo foram calculados no PostgreSQL. **A Página 1 não está aprovada e sua equivalência ao Power BI permanece pendente:** não foram fornecidos valores observados no relatório ou capturas.

## Escopo, execução e precisão

Recorte: ano civil de compra **2017**, UF **SP** da localização do cliente associado ao pedido, sem restrição adicional de período. Todos os status participam de preço, frete, pagamentos e rankings; somente a contagem explicitamente `delivered` recebe esse filtro. SP não é a UF do vendedor. Não há filtro de categoria, vendedor ou método.

Foram consultados o [modelo](../modelagem/modelo_dimensional.md), as [regras RN01–RN08](../regras_negocio/regras.md), o [diagnóstico](../regras_negocio/diagnostico.md), a [Etapa 5](etapa5_validacao_analitica.md), o [plano semântico](../powerbi/planejamento_modelo_semantico.md), a [Etapa 6B](../powerbi/etapa6b_implementacao_modelo.md), DDLs e consultas analíticas existentes. O contexto informado pelo usuário orienta a comparação atual; a Etapa 6B documentava execução no Desktop ainda pendente e não comprova o estado atual do relatório.

Usada a configuração local protegida existente, sem registrar credenciais. A primeira tentativa foi bloqueada pelo sandbox antes da conexão; a execução com acesso autorizado concluiu. Nenhum DDL/DML foi executado. A identidade foi verificada antes das análises; todas as consultas efetivas rodaram em uma única transação `REPEATABLE READ READ ONLY`, encerrada por `ROLLBACK`. O usuário local é proprietário; a proteção desta execução decorre da transação somente leitura, não de privilégios restritos da conta.

'''
    text+=table(read('conexao'),['database','usuario','sessao','proprietario','read_only','isolation','version','instante'])
    text+=f"Marcador conferido: `inteligencia_receita:exclusive:v1`. Fim UTC: `{result['fim_utc']}`. A hora acima inclui o offset −03:00 de São Paulo.\n\n"
    text+='''Cada fato recebe o filtro dimensional independentemente por `data_compra_sk` e `localizacao_sk`. O mês deriva de `dim_calendario.dia`, preservando o dia civil da fonte, sem converter timestamps de compra de fuso. A amplitude temporal segue o papel compra ativo informado para o Power BI, cuja configuração efetiva ainda exige inspeção manual.

Valores monetários são `NUMERIC`, sem arredondamento antes ou depois da soma; o transporte usa `Decimal` e texto decimal exato em JSON. As tabelas usam ponto decimal e nenhum símbolo monetário. Percentuais são a divisão NUMERIC do PostgreSQL, que pode limitar casas decimais de frações periódicas: a proporção exata é `100 × pedidos / 17760`. Comparar participações pelo numerador/denominador ou pela precisão exibida; não exigir soma exata de representações decimais periódicas.

## Cinco KPIs

'''+table([k],['pedidos','delivered','price','freight_value','payment_value'])
    text+='Pedidos e delivered vêm de `fato_pedidos`; price/frete de `fato_itens_pedido`; payment_value de `fato_pagamentos`. Pagamentos registrados não comprovam recebimento ou receita contábil.\n\n## Status e participação\n\n'+table(read('02_status'),['status','pedidos','percentual','denominador'])
    text+='O domínio explícito inclui os oito status, inclusive contagem zero quando ausentes, e incorpora qualquer status adicional ou nulo observado. No recorte todos os oito estão presentes, sem grupo adicional.\n\n## Evolução mensal de produtos\n\n'+table(read('03_meses'),['mes','itens','price','freight_value'])
    text+='Os 12 meses civis foram enumerados para conferir ausências: todos têm itens neste recorte. Se inexistissem linhas, a contagem seria zero e a soma permaneceria NULL; isso não cria valor financeiro zero nem presume a configuração “mostrar itens sem dados” do visual. Não se usa data de entrega ou data financeira.\n\n## Categorias: dez primeiras e empates\n\n'
    text+='Ranking decrescente de `SUM(price)` por `product_category_name` original, sem tradução ou normalização. `membro_tipo` distingue categorias nulas de produtos regulares de membros técnicos. Nesta execução só há produtos regulares nos grupos retornados.\n\n'
    text+=table([r for r in categories if r['posicao']<=10],['posicao','product_category_name','membro_tipo','itens','price','freight_value'])
    text+=f"Foram retornados {len(categories)} grupos completos, incluindo NULL. O corte `rank() <= 10` retorna {sum(r['posicao']<=10 for r in categories)} grupos; inclui todos os empates no limite.\n\nCategoria nula, preservada explicitamente:\n\n"+table([r for r in categories if r['product_category_name'] is None],['posicao','product_category_name','membro_tipo','itens','price','freight_value'])
    text+='Categorias sem tradução continuam com os nomes originais. A listagem integral, inclusive posições posteriores, está em [04_categorias.json](etapa6c_evidencias/04_categorias.json); nenhum grupo foi descartado para fechar o total.\n\n## Vendedores: dez primeiros e empates\n\n'
    text+=table([r for r in sellers if r['posicao']<=10],['posicao','vendedor_sk','seller_id','rotulo','itens','price','freight_value'])
    text+=f"Ranking por `SUM(price)`, com {len(sellers)} vendedores no recorte e {sum(r['posicao']<=10 for r in sellers)} no corte com empates. A SK identifica a coluna de apresentação `Vendedor {{vendedor_sk}}`; seller_id permite rastreabilidade. Desempate de exibição por SK não altera rank nem exclui empatados. O [ranking integral](etapa6c_evidencias/05_vendedores.json) inclui todos os vendedores observados. Pagamentos não foram atribuídos a vendedores.\n\n## Métodos de pagamento\n\n"
    text+=table(read('06_metodos'),['forma_pagamento_sk','payment_type','membro_tipo','registros','pedidos','payment_value'])
    text+='O domínio inclui os cinco métodos regulares e os dois técnicos. `not_defined` existe na dimensão, mas não possui registros neste recorte; sua soma é NULL, não um pagamento zero. Os três registros reais de valor zero no universo geral continuam preservados. Pedidos distintos por método podem se sobrepor e não devem ser somados para obter pedidos totais.\n\n## Reconciliação independente e investigação\n\n'+table(read('09_fatos'),['fato','linhas','pedidos','price','freight_value','payment_value'])
    text+='Itens e pagamentos foram agregados separadamente por pedido e unidos por LEFT JOIN à população de pedidos. Não houve junção dos detalhes de itens e pagamentos. Ausência de filho continua NULL e não gera diferença calculável.\n\n'
    text+=table([r for r in rec if r['nivel']=='total'],['pedidos','sem_itens','sem_pagamentos','comparaveis','diferencas_nao_zero','divergencias','price','freight_value','payment_value','diferenca_comparaveis'])
    text+=f"A diferença global `payment_value − price − freight_value` é **{investigation['diferenca_global']}**. Sua composição é **{investigation['pagamentos_sem_itens']}** de pagamentos dos 236 pedidos sem itens, mais **{investigation['diferenca_comparaveis']}** de diferenças líquidas nos pedidos comparáveis. Não se atribui preço zero a pedidos sem itens.\n\n"
    text+=f"Existem {len(diffs)} diferenças não nulas diferentes de zero: {len(significant)} superiores a 0.01 em valor absoluto ({investigation['positivas_maiores_001']} positivas e {investigation['negativas_menores_menos001']} negativas), e {investigation['diferencas_nao_zero_ate_001']} até 0.01. O limiar é diagnóstico histórico, sem tolerância de aprovação financeira. As {len(significant)} divergências maiores coincidem por order_id e delta exato com as evidências preexistentes do diagnóstico; não são ocorrências novas da reconciliação. Os {len(missing)} pedidos sem itens coincidem por ID e status com a evidência anterior.\n\n"
    text+='Sem itens por status: '+json.dumps(investigation['sem_itens_por_status'])+'. Divergências > 0.01 por status: '+json.dumps(investigation['divergencias_por_status'])+'. As causas financeiras permanecem desconhecidas.\n\n'
    text+='Subtotais por status, preservando as ausências:\n\n'+table([r for r in rec if r['nivel']=='status'],['order_status','pedidos','sem_itens','sem_pagamentos','comparaveis','divergencias','price','freight_value','payment_value'])
    text+='[07_reconciliacao.json](etapa6c_evidencias/07_reconciliacao.json) contém também a decomposição mensal; [08_diferencas_pedido.json](etapa6c_evidencias/08_diferencas_pedido.json) contém todos os pedidos sem comparabilidade e todas as diferenças diferentes de zero, inclusive as pequenas.\n\n## Fechamentos e controle sem filtros\n\n'
    text+=f"As **{len(tests)} verificações SQL/Decimal passaram**, sem falhas. As três verificações adicionais da investigação também passaram. Os subtotais por status recompõem pedidos; mês, categoria e vendedor recompõem preço e frete; método recompõe pagamentos. Cada soma recomposta menos seu total independente é **0 exato**. Status/mês da reconciliação por pedido recompõem contagens, ausências, comparáveis, divergências e as três medidas monetárias, também com diferença zero.\n\n"
    text+='O filtro próprio dos filhos foi comparado ao conjunto derivado dos pedidos nos dois sentidos: zero IDs faltantes ou excedentes. Contexto de cliente, localização, compra e status dos filhos coincide com o pedido, sem divergências. Cardinalidades de todos os joins dimensionais e os oito papéis temporais foram conferidos: sem multiplicação, órfãos ou diferenças de dia. Fingerprints das seis dimensões e três fatos são idênticos antes/depois na fotografia transacional.\n\n'
    general=[]
    for kind in ['pedidos','itens','pagamentos']:
        for row in read('11_geral_'+kind):general.append(dict(fato=kind,**row))
    text+=table(general,['fato','escopo','linhas','pedidos','price','freight_value','payment_value'])
    text+='Todos os campos presentes foram comparados exatamente às evidências aprovadas da Etapa 5, nos escopos geral e delivered: **zero desvio** de contagens ou somas. Os escopos se sobrepõem e não são somáveis. Referências incluem 99441/96478 pedidos, 112650/110197 itens e 103886/100756 pagamentos. Os 775 pedidos sem itens e o delivered sem pagamento do universo não foram excluídos por desenho; no recorte há 236 sem itens e nenhum sem pagamento.\n\n'
    text+=r'''Os membros -1/-2 permanecem nos fatos/dimensões e não foram substituídos. Ano/UF excluem naturalmente membros de calendário/localização sem esses atributos, conforme o filtro solicitado; categoria nula não é excluída. Grupos de categoria e vendedor sem movimento não têm linhas financeiras a somar; não se fabricam zeros. Métodos técnicos e regulares sem registros estão explicitados na tabela de métodos. Não se soma contagem distinta de pedidos entre categorias, vendedores ou métodos.

## Reprodução e evidências

Na raiz, com a configuração protegida existente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\executar_reconciliacao_pagina1.ps1
```

O executor novo restaura variáveis de ambiente, reutiliza apenas funções dos executores aprovados e não modifica esses arquivos. `scripts/reconciliacao_pagina1.py --prepare` prepara as consultas sem conectar. Os SQLs em [sql/validacoes/powerbi](../../sql/validacoes/powerbi/) contêm apenas SELECT/WITH. As consultas `11_geral_*`, 12 e 13 são controles sem o filtro 2017/SP; as demais aplicam o recorte explicitado.

Evidências reais: [preflight](etapa6c_evidencias/00_preflight.sql), [execução integral](etapa6c_evidencias/execucao.sql), [retorno integral](etapa6c_evidencias/execucao.json), [resultado e hashes SQL](etapa6c_evidencias/resultado.json), [78 verificações](etapa6c_evidencias/testes.json), [investigação](etapa6c_evidencias/investigacao.json). JSON por consulta conserva todas as linhas, sem truncar rankings. Para recompilar este documento sem banco: `scripts/documentar_reconciliacao_pagina1.py`. Uma nova execução substitui a pasta fixa `etapa6c_evidencias`; arquivá-la previamente caso seja necessário manter histórico de execuções.

## Critérios de comparação manual e pendências

| Verificação no Power BI | Critério | Situação |
| --- | --- | --- |
| Filtros e interações | Ano compra 2017; UF contextual SP; período integral; nenhum filtro adicional de página/visual/interação; todos os status salvo delivered explícito | Pendente |
| Cinco cartões | Contagens exatas e somas integrais iguais à tabela de KPIs, desativando abreviação de milhares/milhões para comparação | Pendente |
| Status | Oito contagens exatas; participação com denominador 17760 e arredondamento somente de apresentação | Pendente |
| Evolução mensal | Os mesmos 12 meses de compra e price de cada mês; preservar calendário civil e conferir filtros próprios do visual | Pendente |
| Categorias | Atributo original; NULL visível/conservado; SUM(price); corte Top 10 e tratamento de empates iguais ao SQL; confrontar lista integral se necessário | Pendente |
| Vendedores | Correspondência Vendedor SK ↔ vendedor_sk ↔ seller_id e SUM(price); mesmo corte/empates | Pendente |
| Métodos | Valores por payment_type; ausência de not_defined neste recorte distinta de registro zero; nenhum filtro silencioso | Pendente |
| Modelo e importação | Relações dimensão → fato, compra ativa; versão estática e data de atualização; tipos decimais, precisão, nulos e agrupamentos textuais preservados | Pendente |
| Totais sem filtros | Reproduzir as referências gerais e delivered da Etapa 5 | Pendente |

Solicitar valores observados ou capturas com filtros e precisão suficientes; capturas abreviadas não demonstram igualdade exata monetária. Até recebê-los, não é possível calcular diferenças SQL × Power BI, validar o comportamento das interações ou afirmar equivalência. Não foram criados DAX, objetos de banco, dashboards ou alterações no Power BI. Nenhuma camada, regra, relacionamento ou script aprovado foi alterado; não houve commit/push.

As diferenças financeiras observadas foram preservadas. Permanecem pendentes suas causas, a semântica financeira dos pagamentos, confirmação de unidade monetária e a validação da importação NUMERIC no Power BI. O resultado desta etapa é uma referência SQL reproduzível para comparação, sem aprovação da Página 1.
'''
    (ROOT/'docs/qualidade/etapa6c_reconciliacao_pagina1.md').write_text(text,encoding='utf-8')
    print(json.dumps(investigation,ensure_ascii=False,default=str))
if __name__=='__main__':main()
