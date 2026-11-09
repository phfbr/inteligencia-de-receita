# Etapa 6C — Reconciliação analítica da Página 1 (Visão Executiva)

Os resultados abaixo foram calculados no PostgreSQL. **A Página 1 não está aprovada e sua equivalência ao Power BI permanece pendente:** não foram fornecidos valores observados no relatório ou capturas.

## Escopo, execução e precisão

Recorte: ano civil de compra **2017**, UF **SP** da localização do cliente associado ao pedido, sem restrição adicional de período. Todos os status participam de preço, frete, pagamentos e rankings; somente a contagem explicitamente `delivered` recebe esse filtro. SP não é a UF do vendedor. Não há filtro de categoria, vendedor ou método.

Foram consultados o [modelo](../modelagem/modelo_dimensional.md), as [regras RN01–RN08](../regras_negocio/regras.md), o [diagnóstico](../regras_negocio/diagnostico.md), a [Etapa 5](etapa5_validacao_analitica.md), o [plano semântico](../powerbi/planejamento_modelo_semantico.md), a [Etapa 6B](../powerbi/etapa6b_implementacao_modelo.md), DDLs e consultas analíticas existentes. O contexto informado pelo usuário orienta a comparação atual; a Etapa 6B documentava execução no Desktop ainda pendente e não comprova o estado atual do relatório.

Usada a configuração local protegida existente, sem registrar credenciais. A primeira tentativa foi bloqueada pelo sandbox antes da conexão; a execução com acesso autorizado concluiu. Nenhum DDL/DML foi executado. A identidade foi verificada antes das análises; todas as consultas efetivas rodaram em uma única transação `REPEATABLE READ READ ONLY`, encerrada por `ROLLBACK`. O usuário local é proprietário; a proteção desta execução decorre da transação somente leitura, não de privilégios restritos da conta.

| database | usuario | sessao | proprietario | read_only | isolation | version | instante |
| --- | --- | --- | --- | --- | --- | --- | --- |
| inteligencia_receita_db | postgres | postgres | postgres | on | repeatable read | 18.6 | 2026-11-08T16:57:23.042442-03:00 |

Marcador conferido: `inteligencia_receita:exclusive:v1`. Fim UTC: `2026-11-08T19:57:37.958595+00:00`. A hora acima inclui o offset −03:00 de São Paulo.

Cada fato recebe o filtro dimensional independentemente por `data_compra_sk` e `localizacao_sk`. O mês deriva de `dim_calendario.dia`, preservando o dia civil da fonte, sem converter timestamps de compra de fuso. A amplitude temporal segue o papel compra ativo informado para o Power BI, cuja configuração efetiva ainda exige inspeção manual.

Valores monetários são `NUMERIC`, sem arredondamento antes ou depois da soma; o transporte usa `Decimal` e texto decimal exato em JSON. As tabelas usam ponto decimal e nenhum símbolo monetário. Percentuais são a divisão NUMERIC do PostgreSQL, que pode limitar casas decimais de frações periódicas: a proporção exata é `100 × pedidos / 17760`. Comparar participações pelo numerador/denominador ou pela precisão exibida; não exigir soma exata de representações decimais periódicas.

## Cinco KPIs

| pedidos | delivered | price | freight_value | payment_value |
| --- | --- | --- | --- | --- |
| 17760 | 17071 | 2212487.00 | 300998.93 | 2561862.91 |

Pedidos e delivered vêm de `fato_pedidos`; price/frete de `fato_itens_pedido`; payment_value de `fato_pagamentos`. Pagamentos registrados não comprovam recebimento ou receita contábil.

## Status e participação

| status | pedidos | percentual | denominador |
| --- | --- | --- | --- |
| approved | 1 | 0.00563063063063063063 | 17760 |
| canceled | 132 | 0.74324324324324324324 | 17760 |
| created | 1 | 0.00563063063063063063 | 17760 |
| delivered | 17071 | 96.1204954954954955 | 17760 |
| invoiced | 79 | 0.44481981981981981982 | 17760 |
| processing | 102 | 0.57432432432432432432 | 17760 |
| shipped | 170 | 0.95720720720720720721 | 17760 |
| unavailable | 204 | 1.1486486486486486 | 17760 |

O domínio explícito inclui os oito status, inclusive contagem zero quando ausentes, e incorpora qualquer status adicional ou nulo observado. No recorte todos os oito estão presentes, sem grupo adicional.

## Evolução mensal de produtos

| mes | itens | price | freight_value |
| --- | --- | --- | --- |
| 2017-01-01 | 364 | 41534.90 | 5407.87 |
| 2017-02-01 | 706 | 78687.08 | 11200.64 |
| 2017-03-01 | 1128 | 138087.91 | 16525.16 |
| 2017-04-01 | 1018 | 132634.50 | 16048.26 |
| 2017-05-01 | 1586 | 176912.68 | 24196.87 |
| 2017-06-01 | 1470 | 173887.55 | 22527.92 |
| 2017-07-01 | 1822 | 184714.55 | 27077.82 |
| 2017-08-01 | 1966 | 198753.97 | 28596.81 |
| 2017-09-01 | 1817 | 218376.33 | 28152.94 |
| 2017-10-01 | 2084 | 227905.50 | 30883.58 |
| 2017-11-01 | 3437 | 360251.89 | 51391.00 |
| 2017-12-01 | 2646 | 280740.14 | 38990.06 |

Os 12 meses civis foram enumerados para conferir ausências: todos têm itens neste recorte. Se inexistissem linhas, a contagem seria zero e a soma permaneceria NULL; isso não cria valor financeiro zero nem presume a configuração “mostrar itens sem dados” do visual. Não se usa data de entrega ou data financeira.

## Categorias: dez primeiras e empates

Ranking decrescente de `SUM(price)` por `product_category_name` original, sem tradução ou normalização. `membro_tipo` distingue categorias nulas de produtos regulares de membros técnicos. Nesta execução só há produtos regulares nos grupos retornados.

| posicao | product_category_name | membro_tipo | itens | price | freight_value |
| --- | --- | --- | --- | --- | --- |
| 1 | cama_mesa_banho | regular | 2230 | 207464.77 | 32000.56 |
| 2 | relogios_presentes | regular | 896 | 180111.08 | 11054.18 |
| 3 | esporte_lazer | regular | 1639 | 170477.61 | 25241.30 |
| 4 | beleza_saude | regular | 1399 | 157210.18 | 18778.07 |
| 5 | informatica_acessorios | regular | 1164 | 138375.16 | 16992.52 |
| 6 | moveis_decoracao | regular | 1777 | 135928.99 | 27651.32 |
| 7 | cool_stuff | regular | 792 | 129062.19 | 13138.80 |
| 8 | brinquedos | regular | 1004 | 107636.68 | 14754.14 |
| 9 | utilidades_domesticas | regular | 1337 | 97221.41 | 20743.53 |
| 10 | automotivo | regular | 633 | 87592.37 | 9976.85 |

Foram retornados 71 grupos completos, incluindo NULL. O corte `rank() <= 10` retorna 10 grupos; inclui todos os empates no limite.

Categoria nula, preservada explicitamente:

| posicao | product_category_name | membro_tipo | itens | price | freight_value |
| --- | --- | --- | --- | --- | --- |
| 16 | NULL | regular | 389 | 39772.13 | 5142.13 |

Categorias sem tradução continuam com os nomes originais. A listagem integral, inclusive posições posteriores, está em [04_categorias.json](etapa6c_evidencias/04_categorias.json); nenhum grupo foi descartado para fechar o total.

## Vendedores: dez primeiros e empates

| posicao | vendedor_sk | seller_id | rotulo | itens | price | freight_value |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 882 | 4a3ca9315b744ce9f8e9374361493884 | Vendedor 882 | 536 | 53631.03 | 7089.96 |
| 2 | 1561 | 7e93a43ef30c4f03f38b393420bc753a | Vendedor 1561 | 96 | 51883.98 | 1340.95 |
| 3 | 1014 | 53243585a1d6dc2643021fd1853d8905 | Vendedor 1014 | 61 | 47441.17 | 2131.56 |
| 4 | 3025 | fa1c13f2614d7b5c4749cbc52fecda94 | Vendedor 3025 | 106 | 40694.13 | 1192.02 |
| 5 | 1536 | 7c67e1448b00f6e969d365cea6b010ab | Vendedor 1536 | 243 | 34778.45 | 6221.52 |
| 6 | 858 | 4869f7a5dfa277a7dca6462dcf3b52b2 | Vendedor 858 | 162 | 34273.36 | 2262.25 |
| 7 | 844 | 46dc3b2cc0980fb8ec44634e21d2718e | Vendedor 844 | 136 | 32931.49 | 3058.46 |
| 8 | 1506 | 7a67c85e85bb2ce8582c35f2203ad736 | Vendedor 1506 | 252 | 30197.48 | 3175.13 |
| 9 | 2644 | da8622b14eb17ae2831f4ac5b9dab84a | Vendedor 2644 | 276 | 29680.60 | 3683.66 |
| 10 | 2482 | cc419e0650a3c5ba77189a1882b7556a | Vendedor 2482 | 464 | 25618.49 | 4476.38 |

Ranking por `SUM(price)`, com 1411 vendedores no recorte e 10 no corte com empates. A SK identifica a coluna de apresentação `Vendedor {vendedor_sk}`; seller_id permite rastreabilidade. Desempate de exibição por SK não altera rank nem exclui empatados. O [ranking integral](etapa6c_evidencias/05_vendedores.json) inclui todos os vendedores observados. Pagamentos não foram atribuídos a vendedores.

## Métodos de pagamento

| forma_pagamento_sk | payment_type | membro_tipo | registros | pedidos | payment_value |
| --- | --- | --- | --- | --- | --- |
| -2 | NULL | referencia_nao_encontrada | 0 | 0 | NULL |
| -1 | NULL | nao_informado | 0 | 0 | NULL |
| 1 | boleto | regular | 3680 | 3680 | 500491.47 |
| 2 | credit_card | regular | 13584 | 13529 | 1972255.69 |
| 3 | debit_card | regular | 212 | 212 | 20328.54 |
| 4 | not_defined | regular | 0 | 0 | NULL |
| 5 | voucher | regular | 1359 | 798 | 68787.21 |

O domínio inclui os cinco métodos regulares e os dois técnicos. `not_defined` existe na dimensão, mas não possui registros neste recorte; sua soma é NULL, não um pagamento zero. Os três registros reais de valor zero no universo geral continuam preservados. Pedidos distintos por método podem se sobrepor e não devem ser somados para obter pedidos totais.

## Reconciliação independente e investigação

| fato | linhas | pedidos | price | freight_value | payment_value |
| --- | --- | --- | --- | --- | --- |
| fato_pagamentos | 18835 | 17760 | NULL | NULL | 2561862.91 |
| fato_pedidos | 17760 | 17760 | NULL | NULL | NULL |
| fato_itens_pedido | 20044 | 17524 | 2212487.00 | 300998.93 | NULL |

Itens e pagamentos foram agregados separadamente por pedido e unidos por LEFT JOIN à população de pedidos. Não houve junção dos detalhes de itens e pagamentos. Ausência de filho continua NULL e não gera diferença calculável.

| pedidos | sem_itens | sem_pagamentos | comparaveis | diferencas_nao_zero | divergencias | price | freight_value | payment_value | diferenca_comparaveis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 17760 | 236 | 0 | 17524 | 109 | 64 | 2212487.00 | 300998.93 | 2561862.91 | 420.37 |

A diferença global `payment_value − price − freight_value` é **48376.98**. Sua composição é **47956.61** de pagamentos dos 236 pedidos sem itens, mais **420.37** de diferenças líquidas nos pedidos comparáveis. Não se atribui preço zero a pedidos sem itens.

Existem 109 diferenças não nulas diferentes de zero: 64 superiores a 0.01 em valor absoluto (56 positivas e 8 negativas), e 45 até 0.01. O limiar é diagnóstico histórico, sem tolerância de aprovação financeira. As 64 divergências maiores coincidem por order_id e delta exato com as evidências preexistentes do diagnóstico; não são ocorrências novas da reconciliação. Os 236 pedidos sem itens coincidem por ID e status com a evidência anterior.

Sem itens por status: {"unavailable": 204, "canceled": 31, "created": 1}. Divergências > 0.01 por status: {"delivered": 62, "shipped": 2}. As causas financeiras permanecem desconhecidas.

Subtotais por status, preservando as ausências:

| order_status | pedidos | sem_itens | sem_pagamentos | comparaveis | divergencias | price | freight_value | payment_value |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| approved | 1 | 0 | 0 | 1 | 0 | 169.90 | 9.56 | 179.46 |
| canceled | 132 | 31 | 0 | 101 | 0 | 22034.55 | 1996.55 | 28447.59 |
| created | 1 | 1 | 0 | 0 | 0 | NULL | NULL | 160.94 |
| delivered | 17071 | 0 | 0 | 17071 | 62 | 2136258.96 | 291743.66 | 2428416.08 |
| invoiced | 79 | 0 | 0 | 79 | 0 | 11572.86 | 1696.44 | 13269.30 |
| processing | 102 | 0 | 0 | 102 | 0 | 21741.02 | 2697.90 | 24438.92 |
| shipped | 170 | 0 | 0 | 170 | 2 | 20709.71 | 2854.82 | 23571.44 |
| unavailable | 204 | 204 | 0 | 0 | 0 | NULL | NULL | 43379.18 |

[07_reconciliacao.json](etapa6c_evidencias/07_reconciliacao.json) contém também a decomposição mensal; [08_diferencas_pedido.json](etapa6c_evidencias/08_diferencas_pedido.json) contém todos os pedidos sem comparabilidade e todas as diferenças diferentes de zero, inclusive as pequenas.

## Fechamentos e controle sem filtros

As **78 verificações SQL/Decimal passaram**, sem falhas. As três verificações adicionais da investigação também passaram. Os subtotais por status recompõem pedidos; mês, categoria e vendedor recompõem preço e frete; método recompõe pagamentos. Cada soma recomposta menos seu total independente é **0 exato**. Status/mês da reconciliação por pedido recompõem contagens, ausências, comparáveis, divergências e as três medidas monetárias, também com diferença zero.

O filtro próprio dos filhos foi comparado ao conjunto derivado dos pedidos nos dois sentidos: zero IDs faltantes ou excedentes. Contexto de cliente, localização, compra e status dos filhos coincide com o pedido, sem divergências. Cardinalidades de todos os joins dimensionais e os oito papéis temporais foram conferidos: sem multiplicação, órfãos ou diferenças de dia. Fingerprints das seis dimensões e três fatos são idênticos antes/depois na fotografia transacional.

| fato | escopo | linhas | pedidos | price | freight_value | payment_value |
| --- | --- | --- | --- | --- | --- | --- |
| pedidos | delivered | 96478 | 96478 | NULL | NULL | NULL |
| pedidos | geral | 99441 | 99441 | NULL | NULL | NULL |
| itens | delivered | 110197 | 96478 | 13221498.11 | 2198275.64 | NULL |
| itens | geral | 112650 | 98666 | 13591643.70 | 2251909.54 | NULL |
| pagamentos | delivered | 100756 | 96477 | NULL | NULL | 15422461.77 |
| pagamentos | geral | 103886 | 99440 | NULL | NULL | 16008872.12 |

Todos os campos presentes foram comparados exatamente às evidências aprovadas da Etapa 5, nos escopos geral e delivered: **zero desvio** de contagens ou somas. Os escopos se sobrepõem e não são somáveis. Referências incluem 99441/96478 pedidos, 112650/110197 itens e 103886/100756 pagamentos. Os 775 pedidos sem itens e o delivered sem pagamento do universo não foram excluídos por desenho; no recorte há 236 sem itens e nenhum sem pagamento.

Os membros -1/-2 permanecem nos fatos/dimensões e não foram substituídos. Ano/UF excluem naturalmente membros de calendário/localização sem esses atributos, conforme o filtro solicitado; categoria nula não é excluída. Grupos de categoria e vendedor sem movimento não têm linhas financeiras a somar; não se fabricam zeros. Métodos técnicos e regulares sem registros estão explicitados na tabela de métodos. Não se soma contagem distinta de pedidos entre categorias, vendedores ou métodos.

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
