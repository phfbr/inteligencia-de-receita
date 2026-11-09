# Etapa 3 — Investigação de regras de negócio

## Objetivo, fontes e reprodução

Esta investigação detalha as ausências, divergências e cardinalidades observadas no profiling, sem estabelecer regras definitivas de negócio. Foram lidos os CSVs originais de pedidos, itens, pagamentos e clientes. Os nove arquivos da Bronze tiveram seus SHA-256 comparados com o [profiling existente](../qualidade/profiling/resultados.json), antes e depois da execução, sem diferenças. As evidências anteriores foram preservadas.

O script [diagnostico.py](../../scripts/diagnostico.py) reutiliza os nomes de arquivos, as combinações de chaves e a função SHA-256 de `profiling.py`. Usa somente a biblioteca padrão, sem novas dependências. Execução a partir da raiz, com Python 3.10 ou superior:

```text
python scripts/diagnostico.py
python -m unittest discover -s tests -v
```

Como a execução já foi realizada, uma nova reprodução deve usar uma pasta de saída nova, por exemplo:

```text
python scripts/diagnostico.py --output docs/regras_negocio/reproducao_01
```

O script interrompe se a saída já contiver `diagnostico.json`, se os hashes diferirem do profiling ou se as chaves necessárias à agregação forem vazias ou duplicadas. Valores monetários ou datas inválidos causam falha explícita, registrada no log, sem correção ou descarte silencioso. Não houve falha na execução observada. Valores vazios são strings de comprimento zero; não há limpeza, normalização de IDs ou conversão de status.

Os resultados estruturados estão em [diagnostico.json](evidencias/diagnostico.json), com versão do Python, hashes e horários UTC. Os arquivos CSV permitem rastrear os pedidos e grupos que compõem as contagens. O processamento é em memória; o consumo cresce com o volume dos arquivos. Não foram criados Silver, Gold, objetos PostgreSQL, indicadores finais ou dashboards.

## 1. Pedidos sem itens e sem pagamentos

| Status observado | Pedidos sem itens | Pedidos sem pagamentos |
| --- | ---: | ---: |
| approved | 0 | 0 |
| canceled | 164 | 0 |
| created | 5 | 0 |
| delivered | 0 | 1 |
| invoiced | 2 | 0 |
| processing | 0 | 0 |
| shipped | 1 | 0 |
| unavailable | 603 | 0 |
| **Total** | **775** | **1** |

Não há sobreposição: são 776 pedidos distintos com pelo menos uma dessas ausências. Todos os 775 sem itens têm registros de pagamento. A presença de registro não comprova liquidação, recebimento ou ausência de estorno.

O pedido sem pagamento é `bfbd0f9bdef84302105ad712db648a6c`: status `delivered`, três itens, compra em 15/09/2016 12:16:38 e entrega ao cliente em 09/11/2016 07:47:38. O CSV não informa a causa da ausência. Não foi criado pagamento artificial nem presumido valor zero.

Evidência completa: [pedidos_sem_itens_ou_pagamentos.csv](evidencias/pedidos_sem_itens_ou_pagamentos.csv), com status, contagens de filhos e datas de cada pedido.

**Hipótese:** a concentração em `unavailable` e `canceled` pode estar relacionada ao ciclo operacional ou à cobertura da extração. Isso não explica automaticamente os casos em `shipped` e `invoiced` e não autoriza exclusão por status. A causa precisa de documentação da origem.

## 2. Divergências entre pagamentos e itens mais frete

Os valores foram convertidos diretamente das strings originais para `Decimal`. Primeiro foram agregados, de forma independente por `order_id`, `price + freight_value` dos itens e `payment_value` dos pagamentos. Somente depois os dois resultados foram comparados no grão do pedido. Não houve junção entre linhas de itens e pagamentos, multiplicação pelo parcelamento, arredondamento ou conversão para ponto flutuante.

A diferença é `pagamentos − (itens + frete)`. Sinal positivo indica pagamento registrado maior; sinal negativo indica menor. O recorte é estritamente `abs(diferença) > Decimal('0.01')`, apenas para investigação, sem aprovação de tolerância financeira.

Dos 99.441 pedidos, 98.665 têm ambas as fontes: 98.089 apresentam igualdade exata, 273 apresentam diferença não nula de até 0,01 inclusive e 303 ultrapassam 0,01. Os 776 sem uma das fontes ficam explicitamente fora dessa comparação; não foram excluídos das demais análises.

| Status | Diferença negativa | Diferença positiva | Total acima de 0,01 |
| --- | ---: | ---: | ---: |
| delivered | 39 | 260 | 299 |
| canceled | 0 | 2 | 2 |
| shipped | 0 | 2 | 2 |
| Demais status | 0 | 0 | 0 |
| **Total** | **39** | **264** | **303** |

Distribuição conjunta por magnitude absoluta, status e sinal. Os limites inferiores são exclusivos; os superiores, inclusivos.

| Magnitude absoluta | delivered − | delivered + | canceled − | canceled + | shipped − | shipped + | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| (0,01; 0,10] | 21 | 23 | 0 | 0 | 0 | 0 | 44 |
| (0,10; 1] | 1 | 8 | 0 | 0 | 0 | 1 | 10 |
| (1; 10] | 10 | 139 | 0 | 1 | 0 | 1 | 151 |
| (10; 50] | 6 | 83 | 0 | 1 | 0 | 0 | 90 |
| (50; 100] | 1 | 4 | 0 | 0 | 0 | 0 | 5 |
| Acima de 100 | 0 | 3 | 0 | 0 | 0 | 0 | 3 |
| **Total** | **39** | **260** | **0** | **2** | **0** | **2** | **303** |

As diferenças variam de -51,62 a 182,81. O menor valor corresponde a `262118ce178bb3e4590a3adcf6d62e6b`: itens e frete 177,74, pagamentos 126,12. O maior corresponde a `ce6d150fb29ada17d2082f4847107665`: itens e frete 1.403,66, pagamentos 1.586,47. Ambos estão em `delivered`.

Evidência: [divergencias.csv](evidencias/divergencias.csv), com os 303 pedidos, valores exatos, status, sinal, faixa e número de registros de cada fonte. Os decimais aparecem como strings no JSON para preservar sua representação exata. A moeda e o significado contábil não foram comprovados nesta investigação.

**Hipóteses:** arredondamentos da origem, composição de cobranças ou diferenças de cobertura podem contribuir para as divergências. Nenhuma causa foi comprovada, inclusive nas pequenas diferenças. Não se presume desconto, taxa, reembolso, fraude ou erro de carga. O predomínio de pedidos entregues mostra que filtrar apenas esse status não resolve a reconciliação.

## 3. Presença de itens, pagamentos e datas por status

As contagens abaixo têm como unidade o pedido. “Com itens” e “com pagamentos” significam pelo menos um registro correspondente; “ambos” significa presença nas duas fontes. As colunas de datas contam campos preenchidos e interpretáveis, sem afirmar que sua cronologia é consistente.

| Status | Pedidos | Com itens | Com pagamentos | Ambos | Data transportadora | Data entrega cliente | Ambas as datas reais |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| approved | 2 | 2 | 2 | 2 | 0 | 0 | 0 |
| canceled | 625 | 461 | 625 | 461 | 75 | 6 | 6 |
| created | 5 | 0 | 5 | 0 | 0 | 0 | 0 |
| delivered | 96.478 | 96.478 | 96.477 | 96.477 | 96.476 | 96.470 | 96.469 |
| invoiced | 314 | 312 | 314 | 312 | 0 | 0 | 0 |
| processing | 301 | 301 | 301 | 301 | 0 | 0 | 0 |
| shipped | 1.107 | 1.106 | 1.107 | 1.106 | 1.107 | 0 | 0 |
| unavailable | 609 | 6 | 609 | 6 | 0 | 0 | 0 |
| **Total** | **99.441** | **98.666** | **99.440** | **98.665** | **97.658** | **96.476** | **96.475** |

Todos os pedidos têm compra e previsão de entrega preenchidas; previsão não é evidência de entrega realizada. O JSON também registra o preenchimento de aprovação por status.

Há oito pedidos `delivered` sem data de entrega ao cliente e dois sem data da transportadora. Em contrapartida, seis `canceled` têm entrega ao cliente registrada. Não há pedido sem itens com data de entrega ao cliente; o único sem pagamento tem essa data. Status e datas, isoladamente, não definem a elegibilidade comercial ou financeira.

O profiling anterior identificou 166 entregas à transportadora anteriores à compra e 23 entregas ao cliente anteriores à entrega à transportadora. Esses achados continuam como pendências; a tabela desta seção mede presença, sem reclassificar datas ou pedidos.

## 4. Clientes com múltiplos pedidos: status e cronologia

O vínculo usado foi `orders.customer_id → customers.customer_id → customer_unique_id`. Cada `customer_id` tem correspondência única e preenchida; não houve pedido sem mapeamento. Foram encontrados 96.096 identificadores únicos, dos quais 2.997 têm múltiplos pedidos, reunindo 6.342 pedidos. Os outros 93.099 têm um pedido cada. O identificador anonimizado é a unidade observada, sem comprovação de identidade real.

A tabela seguinte considera apenas os 2.997 grupos com múltiplos pedidos no conjunto completo. Um cliente pode aparecer em vários status; as contagens de clientes por status não são aditivas. A coluna final exige ao menos dois pedidos daquele status dentro do grupo.

| Status | Pedidos nesses grupos | Clientes com esse status | Clientes com ≥ 2 pedidos nesse status |
| --- | ---: | ---: | ---: |
| approved | 0 | 0 | 0 |
| canceled | 92 | 83 | 8 |
| created | 1 | 1 | 0 |
| delivered | 6.099 | 2.979 | 2.801 |
| invoiced | 16 | 16 | 0 |
| processing | 15 | 15 | 0 |
| shipped | 75 | 68 | 7 |
| unavailable | 44 | 39 | 5 |
| **Total de pedidos** | **6.342** | — | — |

Dos 2.997 grupos, 2.780 contêm somente pedidos `delivered`, 217 contêm pelo menos um pedido em outro status e 18 não têm nenhum pedido `delivered`. A contagem de 2.801 clientes com pelo menos dois entregues é um recorte descritivo; ainda não representa recompra aprovada.

### Cronologia observada

Os pedidos foram ordenados pela compra, com `order_id` usado apenas para desempate determinístico. Todas as datas de compra desses grupos estão preenchidas. As datas não contêm fuso; dia e horário são os que aparecem no arquivo, sem conversão.

| Recorte exploratório | Clientes | Pares consecutivos |
| --- | ---: | ---: |
| Mesmo timestamp de compra, com precisão de segundo | 290 | 292 |
| Intervalo positivo de até 60 segundos | 485 | 492 |
| Intervalo positivo de até uma hora | 610 | 628 |
| Intervalo positivo de até 24 horas | 678 | 707 |

Os limites de 60 segundos, uma hora e 24 horas são exploratórios, não critérios de sessão ou recompra. As faixas positivas são cumulativas e não incluem empates; clientes também podem aparecer em mais de um recorte. Foram examinados 3.345 pares consecutivos ao todo, dos quais 3.053 têm intervalo estritamente positivo.

Há 923 clientes com ao menos dois pedidos no mesmo dia do calendário e 2.149 com pedidos em dias distintos. Essas contagens podem se sobrepor, pois um cliente pode ter três ou mais pedidos. Mesmo dia não equivale a intervalo de até 24 horas.

Contando todas as combinações de dois pedidos no mesmo timestamp, e não somente vizinhos na sequência, são 294 pares não ordenados. A diferença para os 292 pares consecutivos decorre de grupos com mais de dois pedidos empatados. Um empate no timestamp não comprova simultaneidade real, desdobramento de compra ou duplicação.

O cruzamento dos pares consecutivos com status está no JSON. Entre pedidos com compra estritamente posterior, há 2.841 pares `delivered → delivered`, 30 `canceled → delivered` e 48 `delivered → canceled`. Entre os empates, há 267 pares `delivered → delivered`. Essas setas comparam o status registrado de **pedidos diferentes** na ordem de compra; não representam histórico de mudança de status de um mesmo pedido. Nos empates, a ordem entre status é apenas o desempate técnico e não uma precedência temporal.

Evidências:

- [clientes_multiplos.csv](evidencias/clientes_multiplos.csv): um registro por identificador com múltiplos pedidos, composição de status, primeira/última compra, menor intervalo, dias e empates.
- [sequencia_pedidos.csv](evidencias/sequencia_pedidos.csv): 6.342 pedidos identificados por cliente e posição na sequência, com status, compra e entrega.
- [pares_consecutivos.csv](evidencias/pares_consecutivos.csv): 3.345 pares, horários, status e diferença em segundos.

**Hipóteses:** compras próximas podem refletir uma experiência de compra dividida em pedidos, novas tentativas ou compras independentes. O CSV não permite escolher automaticamente entre essas explicações. Pedidos em datas distintas também dependem de regras de elegibilidade, do período disponível e da estabilidade do identificador para compor uma futura análise de recompra.

## 5. Unicidade e integridade das chaves candidatas

| Fonte | Combinação testada | Registros | Combinações distintas | Componentes vazios | Duplicatas excedentes |
| --- | --- | ---: | ---: | ---: | ---: |
| Pedidos | order_id | 99.441 | 99.441 | 0 | 0 |
| Pedidos | customer_id | 99.441 | 99.441 | 0 | 0 |
| Itens | order_id + order_item_id | 112.650 | 112.650 | 0 | 0 |
| Pagamentos | order_id + payment_sequential | 103.886 | 103.886 | 0 | 0 |
| Clientes | customer_id | 99.441 | 99.441 | 0 | 0 |

Não há referências vazias ou órfãs de itens e pagamentos para pedidos, nem de pedidos para clientes. A verificação usa os identificadores textuais originais. A unicidade de `customer_id` em pedidos vale nesta cópia e não é uma regra garantida para futuras fontes.

`customer_unique_id` não é chave única de linha em clientes: há 96.096 valores distintos em 99.441 linhas, 3.345 ocorrências excedentes e 2.997 grupos repetidos, com máximo de 17. Isso é compatível com o vínculo observado de um identificador único a vários `customer_id`; não é motivo para deduplicar clientes automaticamente.

As verificações não equivalem a restrições implementadas em banco. Não incluem busca exaustiva de chaves alternativas, garantia sobre versões futuras ou regras semânticas para continuidade das sequências numéricas. Não foram escolhidas chaves substitutas ou estruturas dimensionais.

## Verificações, limitações e decisões pendentes

O [log da execução](evidencias/execucao.log) registra a reconciliação das contagens com o profiling e a preservação dos nove hashes. Os [testes](evidencias/testes.log) incluem agregação independente com múltiplos filhos, limite estrito de 0,01, sinal negativo, empate cronológico, duplicação de chave, órfãos e valor não finito. O [registro de verificações](evidencias/verificacoes.log) documenta os códigos de saída, somatórios, integridade dos arquivos de evidência e reprodução em outra pasta.

Origem externa, versão e licença continuam sem comprovação documental. Status são fotografias da extração, sem histórico completo de eventos. Não há evidência suficiente para concluir liquidação, estorno, margem, receita contábil ou causa das divergências. Os resultados descrevem os arquivos analisados e não o comportamento atual da Olist.

Permanecem pendentes:

- esclarecer ausências de itens e pagamentos e como devem aparecer em análises futuras;
- definir o uso de status em cada pergunta comercial ou financeira, inclusive cancelados com entrega registrada;
- investigar composição dos valores e eventual tolerância de reconciliação, sem esconder pequenas divergências;
- distinguir compras independentes, tentativas e desdobramentos antes de definir recompra ou sessão;
- definir se a janela de recompra depende de compra, aprovação ou entrega e quais status são elegíveis;
- confirmar semântica e estabilidade dos identificadores e das sequências com a documentação da origem;
- decidir tratamentos apenas em etapa própria, mantendo rastreabilidade até os registros originais.

Nenhuma regra de negócio foi declarada aprovada. Nenhum registro foi corrigido, excluído ou reclassificado.
