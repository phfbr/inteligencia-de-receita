# Etapa 4C — Tabelas fato Gold

## Execução e evidências

Foram criadas e carregadas somente `gold.fato_pedidos`, `gold.fato_itens_pedido` e `gold.fato_pagamentos`, no banco exclusivo `inteligencia_receita_db`, PostgreSQL 18.6. Os fatos usam as seis dimensões existentes, sem reconstrução, remapeamento de SKs ou alteração de seus atributos. Não foram implementados pontes, views analíticas, DAX, dashboards ou etapas futuras.

A [execução real](etapa4_gold_fatos/20261108T035602100511Z/resultado.json) terminou em `completed_verified`, sem erros inesperados. Foram confirmados dois commits da mesma versão estática, idempotência, rollback, preservação integral da Silver e das dimensões e manutenção dos nove SHA-256 Bronze. As evidências anteriores e os arquivos aprovados permaneceram preservados.

| Ciclo | Resultado | Evidência |
| --- | --- | --- |
| Primeira carga | `committed` | [first.json](etapa4_gold_fatos/20261108T035602100511Z/first.json) |
| Reexecução idempotente | `committed`, resultados idênticos | [second.json](etapa4_gold_fatos/20261108T035602100511Z/second.json) |
| Alteração temporária e falha deliberada antes do commit | `expected_failure`, SQLSTATE `22012` | [rollback.json](etapa4_gold_fatos/20261108T035602100511Z/rollback.json) |
| Conferência integral pós-rollback | Conteúdo e estruturas preservados | Campo `after` do resultado da execução |

A [inspeção inicial somente leitura](etapa4_gold_fatos/20261108T035433730483Z/resultado.json) confirmou as três granularidades e os DDLs reais das dimensões antes da criação dos fatos. O executor também fez uma nova [verificação antes do DDL](etapa4_gold_fatos/20261108T035602100511Z/preflight.json) no ciclo de carga.

## Confronto com o modelo e escolhas de materialização

Foram consultados o [modelo dimensional](../modelagem/modelo_dimensional.md), as [regras RN01–RN08](../regras_negocio/regras.md), a [documentação Silver](etapa4_silver.md), as [dimensões Gold](etapa4_gold_dimensoes.md), seus scripts e os catálogos físicos. As colunas e todas as definições das restrições das dimensões foram comparadas ao [catálogo aprovado da etapa 4B](etapa4_gold_dimensoes/20261108T033107805228Z/catalogo.json), além dos fingerprints que incluem as SKs e atributos.

Não foi encontrada ambiguidade crítica que exigisse mudança de arquitetura. A materialização mantém os três grãos e seus processos separados. As escolhas físicas desta entrega foram:

- chaves naturais nas três PKs, sem SK factual ou sequência;
- todos os atributos originais de negócio dos três arquivos transacionais, com os mesmos tipos da Silver;
- `customer_id`, `order_status` e `order_purchase_timestamp` do pedido também nos filhos, como contexto rastreável permitido pelo modelo, sem nova granularidade;
- FKs apenas para as dimensões aplicáveis e nos papéis de data documentados;
- ausência de totais monetários derivados em `fato_pedidos`, cuja persistência continua aberta no modelo;
- ausência de indicadores finais, flags de recompra, rateios, recebimentos e receita contábil.

O status contextual dos filhos é exatamente o status registrado no pedido da mesma extração. Não representa histórico de transições. A data de compra contextual em pagamentos não é renomeada como data de pagamento ou liquidação.

## Registros, granularidade e chaves

Os quantitativos foram derivados com `COUNT` e agrupamento das chaves naturais no banco, antes do DDL. Os números fornecidos como referência foram confirmados, sem limitar a carga a uma quantidade fixa.

| Fato | PK e grão | Linhas Silver | Linhas Gold | FKs dimensionais |
| --- | --- | ---: | ---: | ---: |
| `fato_pedidos` | `order_id` | 99.441 | 99.441 | 7 |
| `fato_itens_pedido` | `order_id + order_item_id` | 112.650 | 112.650 | 6 |
| `fato_pagamentos` | `order_id + payment_sequential` | 103.886 | 103.886 | 4 |

As três PKs são únicas e não nulas. Seus identificadores, inclusive `order_item_id` e `payment_sequential`, permanecem `TEXT COLLATE "C"`, sem conversão numérica, mudança de caixa ou remoção de caracteres. `order_id` é a dimensão degenerada nos três fatos, e não uma FK entre fatos.

Os 315.977 registros somados são somente um controle de linhas de três grãos distintos. Não representam 315.977 pedidos ou uma medida comercial.

## Atributos e rastreabilidade

| Fato | Atributos originais | Contexto adicional e quantidade de colunas |
| --- | --- | --- |
| Pedidos | `order_id`, `customer_id`, `order_status`, compra, aprovação, entrega à transportadora, entrega ao cliente e previsão | Sete FKs; 15 colunas no total |
| Itens | `order_id`, `order_item_id`, `product_id`, `seller_id`, `shipping_limit_date`, `price`, `freight_value` | Cliente, status e timestamp de compra do pedido; seis FKs; 16 colunas |
| Pagamentos | `order_id`, `payment_sequential`, `payment_type`, `payment_installments`, `payment_value` | Cliente, status e timestamp de compra do pedido; quatro FKs; 12 colunas |

Os timestamps são `TIMESTAMP WITHOUT TIME ZONE`, copiados integralmente, sem truncamento, arredondamento, atribuição ou conversão de fuso. A extração de dia civil é usada exclusivamente para localizar o membro de calendário; não substitui o timestamp original. Os textos originais de campos convertidos continuam disponíveis em `_raw_record` da Silver, recuperáveis pela chave natural única de cada ocorrência. Não houve regravação dos CSVs.

Não foram duplicadas as colunas técnicas de arquivo/posição da Silver nos fatos: a rastreabilidade usa o grão natural preservado e a cadeia de hashes das evidências. Não foi escolhido um `customer_id` representativo de uma identidade, e não se atribuiu localização permanente a `customer_unique_id`.

## FKs físicas e papéis de calendário

Todas as 17 FKs são `BIGINT NOT NULL`, validadas, não diferíveis, com `ON UPDATE NO ACTION` e `ON DELETE NO ACTION`. Referenciam exclusivamente PKs das dimensões existentes. Não há FK, cascata ou ponte entre fatos. As [restrições físicas do PostgreSQL](https://www.postgresql.org/docs/18/ddl-constraints.html) foram verificadas em catálogo e por tentativas controladas de violação.

| Fato | FKs materializadas | Destino |
| --- | --- | --- |
| Pedidos | `cliente_sk`, `localizacao_sk` | `dim_clientes`, `dim_localizacao` |
| Pedidos | `data_compra_sk`, `data_aprovacao_sk`, `data_transportadora_sk`, `data_entrega_sk`, `data_previsao_entrega_sk` | Cinco relações independentes com `dim_calendario.data_sk` |
| Itens | `cliente_sk`, `localizacao_sk`, `produto_sk`, `vendedor_sk` | Dimensões correspondentes |
| Itens | `data_compra_sk`, `data_limite_envio_sk` | Compra do pedido e limite de envio do próprio item, no calendário |
| Pagamentos | `cliente_sk`, `localizacao_sk`, `forma_pagamento_sk`, `data_compra_sk` | Cliente/localização do pedido, método do registro e dia de compra |

O [catálogo real dos fatos](etapa4_gold_fatos/20261108T035602100511Z/catalogo_fatos.json) confirmou três PKs e 17 FKs. No PostgreSQL 18 também foram observadas 22 restrições NOT NULL: cinco componentes de PK e 17 referências dimensionais. São 43 colunas e 42 restrições no conjunto dos três fatos, além de três índices de PK.

A criação de FKs adiciona os mecanismos internos de integridade referencial do PostgreSQL. Esses triggers internos são esperados e não correspondem a funções ou triggers de negócio implementados pelo projeto. As colunas, SKs, índices e restrições originais das dimensões não foram reconstruídos ou alterados.

## Resolução dimensional e membros especiais

A identidade analítica é resolvida por `pedido.customer_id → Silver clientes.customer_unique_id → dim_clientes`. A localização usa o mesmo registro de cliente ligado ao pedido, comparando separadamente e de forma exata prefixo de CEP, cidade e UF com `dim_localizacao`. Não se usa geolocalização bruta.

Os itens e pagamentos resolvem esse contexto por seu `order_id` no arquivo Silver de pedidos, com junções à esquerda para não ocultar registros. Produto e vendedor vêm do próprio item; o método vem do próprio registro de pagamento. As junções às dimensões usam identidades naturais únicas, e sua cardinalidade foi comparada à origem antes de inserir os fatos.

- `-1` significa informação ausente: chave ou componente obrigatório não informado, ou timestamp ausente naquele papel.
- `-2` significa referência preenchida e não encontrada. Um pedido referenciado pelo filho mas ausente da origem torna o contexto desconhecido por referência, não por ausência de informação.
- Timestamps ausentes continuam nulos no atributo original e recebem `-1` na respectiva FK de calendário; não recebem uma data fictícia.
- Não foram criados novos membros, pedidos, itens ou pagamentos artificiais. `not_defined` continua resolvendo o método regular existente.

Na versão executada, nenhuma das 17 referências usou `-2`. A resolução foi exata para todas as chaves preenchidas. O uso de `-1` ficou restrito aos papéis abaixo em `fato_pedidos`:

| FK | Ocorrências `-1` | Ocorrências `-2` |
| --- | ---: | ---: |
| `data_aprovacao_sk` | 160 | 0 |
| `data_transportadora_sk` | 1.783 | 0 |
| `data_entrega_sk` | 2.965 | 0 |
| Demais FKs de pedidos | 0 | 0 |
| Todas as FKs de itens e pagamentos | 0 | 0 |

As 4.908 ausências são contagens de papéis, não necessariamente pedidos distintos. A estrutura e a comparação integral preservam a diferença entre campo não informado, referência não encontrada e evento não comprovado. Dados de outra versão com falhas de conversão não são aceitos automaticamente como este conjunto estático aprovado.

## Medidas exatas e ausência de multiplicação

`price`, `freight_value` e `payment_value` são `NUMERIC` sem restrição de precisão/escala que cause arredondamento. As duas primeiras medidas existem somente no fato de itens; a terceira, somente no de pagamentos. Não há passagem por ponto flutuante ou coluna de receita/recebimento.

`payment_installments` foi mantido como atributo numérico não aditivo, com o mesmo tipo e valor da Silver. Não multiplica `payment_value` e não gera parcelas ou datas de recebimento. Identificadores de item/sequência não são quantidades. Contagens correspondem às linhas de cada grão.

| Medida | Silver | Gold | Diferença de carga |
| --- | ---: | ---: | ---: |
| `price` | 13.591.643,70 | 13.591.643,70 | 0 |
| `freight_value` | 2.251.909,54 | 2.251.909,54 | 0 |
| `payment_value` | 16.008.872,12 | 16.008.872,12 | 0 |

Além das somas, cada valor foi comparado em seu registro completo e respectiva chave natural. Igualdade de total, sozinha, não seria suficiente para aceitar a carga.

A carga de itens não consulta linhas de pagamentos e a de pagamentos não consulta linhas de itens. As únicas junções de construção são com pedido/cliente Silver e dimensões de identidade única. A PK impede duplicação de grão e as contagens antes/depois comprovam que os lookups não multiplicaram ou eliminaram linhas. Não foi implementado rateio de pagamento por produto, vendedor ou método combinado com item.

## Reconciliação por pedido e exceções preservadas

A validação agrega itens e pagamentos **independentemente por pedido**, antes de combinar os resultados com o universo de pedidos. Foram comparados integralmente os 99.441 registros dessa reconciliação entre Silver e Gold, incluindo status, número de filhos, preço, frete, pagamento e diferença assinada. A consulta não junta os dois detalhes entre si.

| Verificação | Resultado Gold, igual à Silver |
| --- | ---: |
| Pedidos sem itens | 775 |
| Pedidos sem pagamento | 1 |
| Pedidos comparáveis monetariamente | 98.665 |
| Diferença absoluta superior a 0,01 | 303 |
| Diferenças positivas acima de 0,01 | 264 |
| Diferenças negativas abaixo de -0,01 | 39 |
| Menor diferença assinada | -51,62 |
| Maior diferença assinada | 182,81 |

Os pedidos sem uma das fontes não recebem soma ou diferença artificial igual a zero. A diferença permanece não comparável nesses casos. As 303 exceções seguem distribuídas em 299 `delivered`, dois `canceled` e dois `shipped`, sem correção ou exclusão.

O limiar de 0,01 continua apenas o recorte diagnóstico das etapas anteriores. As somas globais das três medidas têm universos distintos e não são equiparadas entre si. A moeda e a causa das diferenças não foram inferidas.

## Preservação dos status

Nenhuma carga filtra `delivered`. Todos os 99.441 pedidos foram mantidos, incluindo os 625 cancelados, os 775 sem itens e o pedido sem pagamento. O status propagado nos filhos é o do respectivo pedido da origem.

| Status | Pedidos | Linhas de itens | Registros de pagamento |
| --- | ---: | ---: | ---: |
| approved | 2 | 3 | 2 |
| canceled | 625 | 542 | 664 |
| created | 5 | 0 | 5 |
| delivered | 96.478 | 110.197 | 100.756 |
| invoiced | 314 | 359 | 325 |
| processing | 301 | 357 | 319 |
| shipped | 1.107 | 1.185 | 1.166 |
| unavailable | 609 | 7 | 649 |

As colunas não têm o mesmo grão e não devem ser somadas como pedidos. A ausência de itens em `created`, por exemplo, não eliminou seus pedidos ou pagamentos. RN02 permanece uma regra de recorte comercial futuro, e RN07 não foi materializada como indicador de recompra.

## Testes executados

Os [13 testes locais](etapa4_gold_fatos/testes_locais.log) passaram. Eles verificam os grãos, quantidade/destino das FKs, tipos exatos, preservação de identificadores e timestamps, ausência de filtro comercial, contexto de localização, agregação independente, proteção do catálogo aprovado, restrição do escopo de escrita e correspondência entre SQL versionado e gerador.

Nos ciclos reais de escrita foram executados **23 testes físicos de rejeição** por ciclo: três tentativas de PK repetida, três de chave primária nula e 17 de FK inválida. Cada caso exige a exceção específica (`unique_violation`, `not_null_violation` ou `foreign_key_violation`), sem capturar erros genéricos como sucesso. As alterações de teste ficam em subtransações revertidas; nenhum registro sintético é persistido.

Cada ciclo também verifica a estrutura em catálogo, o conjunto completo de fatos contra sua projeção Silver/dimensões com `EXCEPT ALL` nos dois sentidos, contagens, presença de todas as referências, somas exatas e reconciliação por pedido. As comparações incluem todos os atributos e as 17 SKs resolvidas, não apenas amostras.

O teste final de atomicidade altera temporariamente o status de um único pedido Gold para um valor técnico de teste, confirma que houve alteração e provoca divisão por zero antes do commit. O SQLSTATE precisa ser exatamente `22012`. A conferência somente leitura posterior exige novamente o conteúdo integral original e os fingerprints iguais aos das duas cargas válidas; o valor de teste não permaneceu na tabela.

## Preservação da Bronze, Silver e dimensões

Os nove arquivos Bronze mantiveram os hashes da referência. A verificação integral Silver antes e depois compreende suas nove tabelas e 1.550.922 registros, campos originais, tipos, nulos, chaves, somas, metadados de origem e fingerprints por registro. Não houve escrita na Silver.

Os seis fingerprints dimensionais coincidem tanto com a referência aprovada da etapa 4B quanto entre o início e o fim desta etapa. A comparação inclui SKs, identidades, atributos e os membros especiais. Os OIDs e identificadores de arquivo das quinze tabelas de origem — nove Silver e seis dimensões — também permaneceram iguais, assim como as colunas e definições originais das restrições dimensionais.

As dimensões não receberam inserts, updates, exclusões ou DDL de reconstrução. Os mecanismos internos adicionados pelas FKs não mudam suas SKs nem constituem SCD2. As exceções existentes, inclusive categorias sem tradução e divergências financeiras, continuam preservadas na origem.

## Proteção, transação e idempotência

A conexão reutiliza a configuração local protegida, sem senha em argumentos, SQL, logs ou arquivos versionados. A rotina verifica o banco nominal, owner, marcador de exclusividade, schemas, objetos esperados e compatibilidade antes de criar tabelas. Fato preexistente sem identificação, estrutura incompatível ou FK divergente causa recusa, sem adoção ou remoção automática.

O executor adapta localmente a allowlist da etapa 4B para permitir somente os três fatos e seus índices de PK adicionais. Os arquivos validados das etapas anteriores não foram modificados, e não foi liberada a criação de objetos arbitrários. As verificações anteriores de Silver/dimensões são reutilizadas em leitura.

Cada carga utiliza transação `REPEATABLE READ`, lock consultivo do projeto e locks `SHARE` em todas as tabelas Silver e dimensões. Isso mantém estáveis as fontes de resolução durante a construção. Não há `DROP`, `TRUNCATE`, cascata, ponte ou atualização de atributos na carga regular.

Na versão estática, a carga usa `ON CONFLICT` somente nas PKs definidas, com `DO NOTHING`, seguido de comparação integral. O comportamento está documentado em [INSERT do PostgreSQL](https://www.postgresql.org/docs/18/sql-insert.html). Uma linha preexistente diferente não é corrigida silenciosamente: a comparação falha e reverte a transação. O `WHERE TRUE` do `INSERT SELECT` evita ambiguidade sintática com `ON CONFLICT`; não filtra registros.

As duas cargas apresentaram os mesmos fingerprints, contagens, status, medidas, referências e resultados de reconciliação. Após a falha deliberada, esses mesmos resultados foram confirmados novamente. Não se promete atualização incremental ou migração automática para outra versão de dados.

## Arquivos e reprodução

Arquivos criados para esta etapa:

- [scripts/gold_fatos.py](../../scripts/gold_fatos.py) e [scripts/executar_gold_fatos.ps1](../../scripts/executar_gold_fatos.ps1);
- [sql/gold/003_fatos.sql](../../sql/gold/003_fatos.sql) e [sql/gold/004_carga_fatos.sql](../../sql/gold/004_carga_fatos.sql);
- [sql/validacoes/gold_fatos.sql](../../sql/validacoes/gold_fatos.sql);
- [tests/test_gold_fatos.py](../../tests/test_gold_fatos.py);
- este relatório e evidências em `docs/qualidade/etapa4_gold_fatos/`.

Não há nova dependência ou alteração de `requirements.txt`. O wrapper usa Python e psql locais já verificados, importando a credencial protegida apenas para o processo de execução e restaurando seu ambiente ao terminar.

```text
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\executar_gold_fatos.ps1 -Mode inspect
python -m unittest discover -s tests -p test_gold_fatos.py -v
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\executar_gold_fatos.ps1 -Mode run
```

`inspect` não cria tabelas: valida destino, Silver e dimensões, lê seus DDLs reais e deriva as contagens dos grãos. `run` executa as duas cargas, os testes físicos, a falha deliberada e a conferência final. Os diretórios de evidência usam horário UTC e não sobrescrevem execuções anteriores. O comando `python` pressupõe um interpretador funcional; o wrapper usa a instalação local já validada.

O [registro final de verificações](etapa4_gold_fatos/20261108T035602100511Z/verificacoes_finais.json) consolida dados reais, catálogo, somas, hashes e a cadeia das evidências aprovadas usadas como entrada.

## Limitações e pendências

Permanecem dependentes de evidência a procedência/licença da cópia, moeda e causa das inconsistências de datas, categorias e valores. Nenhuma causa foi inventada e nenhuma tolerância de negócio foi promovida a regra de correção.

Os executores anteriores de Silver e dimensões mantêm suas allowlists fechadas e recusam objetos de fases posteriores. As conferências desta etapa usam uma extensão local e restrita dessas proteções. Recargas coordenadas de camadas anteriores, evolução de fonte ou manutenção de chaves para novas versões exigem especificação própria, respeitando as FKs agora existentes; não se deve desativar as proteções ou usar cascatas para forçar uma atualização.

Totais derivados em pedidos, novos indicadores, rateios e consumo analítico continuam fora deste escopo. Os fatos não transformam pagamentos em recebimentos ou valores de itens em receita contábil. Não foram alteradas decisões arquiteturais do modelo aprovado.

A Etapa 4C não está declarada aprovada.
