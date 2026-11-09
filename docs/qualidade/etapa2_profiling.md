# Etapa 2 — Inventário e profiling da Bronze

## Execução e procedência

Em 7 de novembro de 2026, os nove CSVs esperados foram encontrados em `data/bronze/`. Nenhum download foi realizado. O conjunto foi tratado como a cópia local disponibilizada para este projeto. Não foram encontrados documentos de origem, identificador de versão, comprovante de download ou licença junto aos arquivos. Portanto, a procedência externa, a versão publicada e a autenticidade oficial permanecem por confirmar. Os SHA-256 identificam os bytes analisados, mas não substituem a comparação com uma fonte confiável.

A cobertura observada de `order_purchase_timestamp` vai de 04/09/2016 21:15:19 a 17/10/2018 17:30:18, sem informação de fuso no CSV. Esse intervalo descreve os dados locais, não uma versão do conjunto ou sua data de obtenção.

O script [profiling.py](../../scripts/profiling.py) foi executado com Python 3.14, apenas com a biblioteca padrão. Os arquivos foram abertos somente para leitura. Os nove hashes foram comparados antes e depois do profiling e reconferidos ao final, sem diferenças.

## Inventário observado

As linhas abaixo são registros CSV sem o cabeçalho, não linhas físicas: comentários podem conter quebras de linha dentro de campos entre aspas.

| Arquivo | Bytes | Registros | Colunas |
| --- | ---: | ---: | ---: |
| olist_customers_dataset.csv | 9.033.957 | 99.441 | 5 |
| olist_geolocation_dataset.csv | 61.273.883 | 1.000.163 | 5 |
| olist_orders_dataset.csv | 17.654.914 | 99.441 | 8 |
| olist_order_items_dataset.csv | 15.438.671 | 112.650 | 7 |
| olist_order_payments_dataset.csv | 5.777.138 | 103.886 | 5 |
| olist_order_reviews_dataset.csv | 14.451.670 | 99.224 | 7 |
| olist_products_dataset.csv | 2.379.446 | 32.951 | 9 |
| olist_sellers_dataset.csv | 174.703 | 3.095 | 4 |
| product_category_name_translation.csv | 2.613 | 71 | 2 |

Total: 1.550.922 registros, distribuídos entre grãos distintos. Esse total é somente um controle do inventário. Nomes das colunas e SHA-256 completos estão em [inventario.csv](profiling/inventario.csv); o detalhamento por coluna está em [resultados.json](profiling/resultados.json).

## Método e alcance das verificações

O parser usa CSV estrito e UTF-8 com suporte a BOM. São contados registros com largura diferente do cabeçalho, duplicatas exatas excedentes, valores distintos, campos vazios e campos contendo somente espaços. Vazio significa string de comprimento zero; textos como `NULL`, `NA` ou `not_defined` não são convertidos automaticamente em nulos. As frequências permitem examinar categorias, status, meios de pagamento e parcelamento.

Tipos são inferências de parseabilidade, não definições de esquema. Identificadores e CEPs continuam sendo texto na fonte, mesmo quando parecem números. Para campos numéricos selecionados são calculados mínimo, máximo, média, quartis, percentil 95, zeros e negativos. Quantis usam interpolação linear na posição `(n - 1) × p`. Datas são verificadas com `datetime.fromisoformat`, sem conversão de fuso ou correção. Nenhuma regra semântica definitiva é imposta.

As chaves candidatas são combinações explicitamente selecionadas no script, avaliadas por unicidade e preenchimento; não houve busca exaustiva de todas as combinações. A integridade referencial cobre pedidos–clientes, itens–pedidos, pagamentos–pedidos, itens–produtos, itens–vendedores, avaliações–pedidos e produtos–tradução. Não inclui ainda vinculação geográfica por CEP nem validação externa de cidades, estados ou coordenadas.

## Resultados observados

### Qualidade e preenchimento

- Não foram encontrados registros com quantidade incorreta de colunas ou valores não interpretáveis nos campos numéricos e de data selecionados.
- Geolocalização tem 261.831 duplicatas exatas excedentes e 19.015 prefixos de CEP distintos; um prefixo aparece em até 1.146 registros. Nenhum registro foi removido.
- Pedidos têm 160 aprovações, 1.783 datas de entrega à transportadora e 2.965 datas de entrega ao cliente vazias.
- Produtos têm 610 categorias e campos de descrição/nome/fotos vazios; peso e cada campo de dimensão têm dois vazios. Há 13 produtos em duas categorias não vazias sem correspondência na tradução.
- Avaliações têm 87.656 títulos e 58.247 comentários vazios. `review_id` apresenta 814 ocorrências excedentes; `order_id`, 551. A combinação dos dois é única e preenchida nesta cópia. Há 547 pedidos com mais de uma avaliação e 768 pedidos sem avaliação.
- As demais fontes não têm duplicatas exatas. Isso não significa ausência de problemas de negócio.

### Chaves e cardinalidades

`order_id`, `customer_id` em clientes, `product_id`, `seller_id` e a categoria na tradução são únicos e preenchidos em seus arquivos. As combinações `order_id + order_item_id` e `order_id + payment_sequential` também são únicas e preenchidas. Essas observações não definem as chaves do futuro modelo dimensional.

Não foram encontrados órfãos nas relações de pedidos com clientes, itens com pedidos/produtos/vendedores, pagamentos com pedidos e avaliações com pedidos. A ausência de filhos em algumas relações foi medida separadamente:

- 775 pedidos não têm itens; um pedido não tem pagamento.
- 9.803 pedidos têm múltiplos itens; 2.961 têm múltiplos registros de pagamento.
- Há de zero a 21 itens e de zero a 29 pagamentos por pedido, incluindo pedidos sem registros correspondentes.
- Há 275 pedidos com multiplicidade nas duas fontes. Uma junção interna direta de pedidos × itens × pagamentos produziria 117.601 linhas, contra 112.647 itens em pedidos com pagamento e 103.056 pagamentos em pedidos com itens. Somar valores nesse resultado multiplicaria contribuições; perder pedidos sem correspondência também altera o universo analisado.

Clientes apresentam 99.441 `customer_id` e 96.096 `customer_unique_id` distintos. Cada `customer_id` corresponde a exatamente um `customer_unique_id` e a um pedido nesta cópia. Há 2.997 identificadores únicos ligados a múltiplos `customer_id` e múltiplos pedidos, com máximo de 17. Não houve pedido sem vínculo inequívoco com cliente. Contar `customer_id` como pessoa recorrente ocultaria essa relação.

### Datas, status e valores

Foram observados 166 registros com entrega à transportadora anterior à compra entre 97.658 pares comparáveis, e 23 entregas ao cliente anteriores à entrega à transportadora entre 96.475 pares comparáveis. O status `delivered` aparece em oito pedidos sem data de entrega ao cliente. São sinais para investigação, sem correção automática.

| Status | Pedidos |
| --- | ---: |
| delivered | 96.478 |
| shipped | 1.107 |
| canceled | 625 |
| unavailable | 609 |
| invoiced | 314 |
| processing | 301 |
| created | 5 |
| approved | 2 |

Meios de pagamento aparecem em 76.795 registros de cartão de crédito, 19.784 de boleto, 5.775 de voucher, 1.529 de cartão de débito e três `not_defined`. São contagens de registros de pagamento, não de pedidos exclusivos. Há dois registros com zero parcelas e nove pagamentos com valor zero. O parcelamento varia de zero a 24; isso não autoriza multiplicar `payment_value` pelo número de parcelas.

O preço por item varia de 0,85 a 6.735,00, com mediana 74,99; o frete varia de zero a 409,68, com 383 valores zero. Pagamentos variam de zero a 13.664,08, com mediana 100,00. A unidade monetária não foi comprovada por metadados nesta execução; não se atribui significado contábil a esses valores.

A comparação diagnóstica entre soma de pagamentos e soma de preço mais frete foi feita separadamente por pedido, antes de combinar as fontes. Entre 98.665 pedidos com ambas as informações, 303 têm diferença absoluta superior a 0,01; as diferenças variam de -51,62 a 182,81. A conta usa `Decimal` para evitar resíduos binários; as estatísticas de distribuição são exportadas como números de ponto flutuante. O limite de 0,01 é apenas um recorte exploratório, não uma tolerância aprovada ou indicador definitivo.

## Hipóteses e limitações

Múltiplos pedidos sob um `customer_unique_id` permitem investigar recompra, mas não bastam para definir uma taxa: status elegíveis, janela de observação, pedidos simultâneos e identificação anonimizada ainda precisam de regras. Os 2.997 identificadores não são apresentados como clientes com recompra validada.

As divergências de valores, datas e categorias podem envolver particularidades da origem ou problemas de qualidade. A causa não foi determinada. Ausência de itens ou pagamentos não foi classificada automaticamente como erro, e pagamentos não foram equiparados a receita contábil ou lucro. As duplicatas geográficas não devem ser eliminadas antes de compreender o grão e o uso dessa fonte.

O profiling descreve integralmente os arquivos locais nos testes definidos, mas não comprova representatividade, completude externa ou consistência com sistemas da Olist. Não define fatos, dimensões, métricas definitivas ou tratamentos para Silver e Gold.

## Logs, verificações e erros de execução

- [execucao.log](profiling/execucao.log) registra a execução final; `resultados.json` contém versão do Python, horários UTC e lista de erros vazia.
- [testes.log](testes.log) registra os testes sintéticos de CSV com quebra de linha, duplicação, campos vazios, largura incorreta, preservação de bytes, valores inválidos, datas, quantis, multiplicação de linhas e aritmética decimal.
- [verificacoes.log](verificacoes.log) registra quatro testes aprovados, a conferência independente de tamanhos e hashes, e o teste de interrupção sem gerar relatórios quando faltam CSVs.
- O alias `python.exe` no PATH e o lançador `py.exe` apontaram para WindowsApps e falharam com “Não é possível o acesso ao arquivo pelo sistema”. Foi usado o executável existente em `<diretório local do Python>\python.exe`, sem instalação.
- A inspeção com `ConvertFrom-Json` do Windows PowerShell falhou por uma chave de nome vazio nas frequências. A leitura foi feita com `json` do Python; o JSON válido preserva a categoria vazia.
- O redirecionamento inicial de testes pelo PowerShell apresentou saída padrão de erro como `NativeCommandError`, embora os testes indicassem sucesso. A execução foi repetida com captura por `subprocess`, confirmando código zero e gravando log sem essa ambiguidade.
- A primeira exploração usava ponto flutuante na reconciliação monetária. O cálculo foi ajustado para `Decimal` e o profiling foi reexecutado; as evidências publicadas correspondem à execução final.

## Pendências

Confirmar procedência, versão e licença do conjunto; esclarecer categorias sem tradução e semântica de campos; investigar datas e valores divergentes; definir regras de status, recompra, parcelamento e agregação; ampliar verificações geográficas se necessárias; decidir critérios de qualidade e tratamentos em etapa própria. Silver, Gold, PostgreSQL e Power BI não foram implementados. A Etapa 2 permanece sem declaração de aprovação.
