# Etapa 5 — Validação analítica SQL

## Execução e referências

As 24 consultas foram executadas em `inteligencia_receita_db`, PostgreSQL 18.6, em 8 de novembro de 2026, das 04:21:10 às 04:22:43 UTC. A conexão protegida confirmou o marcador de exclusividade do projeto. A execução usou `REPEATABLE READ READ ONLY`, com encerramento por `ROLLBACK`, sem operações de escrita, criação de objetos ou testes que alterassem registros.

Foram consultados o [modelo dimensional](../modelagem/modelo_dimensional.md), as [RN01–RN08](../regras_negocio/regras.md), a [Silver](etapa4_silver.md), as [dimensões](etapa4_gold_dimensoes.md), os [fatos](etapa4_gold_fatos.md) e os componentes existentes. Nenhum desses arquivos foi modificado.

O [resultado real](etapa5_validacao_analitica/20261108T042110748288Z/resultado.json) registra **130 verificações sem falhas**, além de [três testes locais](etapa5_validacao_analitica/testes_unitarios.log) das proteções do executor e do transporte decimal. As evidências completas estão em [20261108T042110748288Z](etapa5_validacao_analitica/20261108T042110748288Z/), em JSON e CSV por análise. Os arquivos contêm todos os grupos retornados, sem truncamento para rankings.

Uma tentativa anterior, [20261108T042053644394Z](etapa5_validacao_analitica/20261108T042053644394Z/erro.json), falhou no parser local: o prefixo reutilizado retorna também um booleano do `set_config`. O parser foi corrigido para consumir apenas as linhas JSON, preservando `Decimal`. Não houve erro de autenticação nem alteração no banco. O log dessa tentativa foi preservado.

## Definições e grãos

| Processo | Grão | Contagem e medidas |
| --- | --- | --- |
| Pedidos | `order_id` | Linhas e pedidos distintos; todos os status preservados |
| Itens | `order_id + order_item_id` | Linhas de itens, pedidos distintos, `SUM(price)` e `SUM(freight_value)` separados |
| Pagamentos | `order_id + payment_sequential` | Registros, pedidos distintos e `SUM(payment_value)` |
| Clientes | `customer_unique_id` | Identidades distintas, pedidos por identidade e dias elegíveis para RN07 |

`geral` inclui todos os status; `delivered` é um subconjunto, definido exclusivamente pelo status original. Esses escopos se sobrepõem e não podem ser somados. A ausência de data de entrega não remove um pedido `delivered`.

O mês é o mês civil de compra, derivado da dimensão no lado Gold e diretamente do timestamp no lado Silver. Em pagamentos, representa contexto de compra, não data de pagamento, liquidação ou recebimento. Não há inferência de fuso. Meses sem ocorrências não recebem linhas artificiais de valor zero. A contagem de linhas de itens não presume uma unidade física adicional além da granularidade da origem.

As somas usam `NUMERIC` no servidor, sem tolerância de arredondamento na comparação Silver × Gold. O transporte Python usa `Decimal`; valores decimais aparecem como texto exato no JSON. Nenhum resultado recebe símbolo de moeda. Pagamentos não representam receita contábil ou fluxo de caixa. Não se soma `payment_installments`.

## Resultados observados

| Resultado | Geral | Somente `delivered` |
| --- | ---: | ---: |
| Pedidos distintos | 99.441 | 96.478 |
| Linhas de itens | 112.650 | 110.197 |
| Pedidos com itens | 98.666 | 96.478 |
| Valor bruto de produtos — `price` | 13.591.643,70 | 13.221.498,11 |
| Frete — `freight_value` | 2.251.909,54 | 2.198.275,64 |
| Registros de pagamento | 103.886 | 100.756 |
| Pedidos com pagamentos | 99.440 | 96.477 |
| Valor registrado — `payment_value` | 16.008.872,12 | 15.422.461,77 |

Distribuição dos pedidos: `approved` 2; `canceled` 625; `created` 5; `delivered` 96.478; `invoiced` 314; `processing` 301; `shipped` 1.107; `unavailable` 609. A soma por status e a soma por mês reproduzem o total em cada escopo.

As compras dos pedidos vão de **2016-09-04 21:15:19 a 2018-10-17 17:30:18**. O último mês de compra com pedidos `delivered` é agosto de 2018. Os itens têm compra contextual até 2018-09-03; portanto, sua cobertura temporal não deve ser presumida idêntica à dos pedidos. O calendário chega a 2020-04-09 por causa do limite de envio observado, não por compras nesse período. Os oito papéis temporais materializados nos três fatos foram verificados, sem diferenças entre o dia da dimensão e o timestamp original. Continuam ausentes 160 aprovações, 1.783 entregas à transportadora e 2.965 entregas ao cliente; essas ausências resolvem para `-1`, sem datas fictícias.

As análises de produtos, categorias e vendedores usam exclusivamente valores dos itens. Os totais de linhas, produtos e frete fecham exatamente em todos esses agrupamentos. Há 1.603 linhas de itens sem categoria no geral, das quais 1.537 em `delivered`; os produtos permanecem identificados. As categorias originais `pc_gamer` e `portateis_cozinha_e_preparadores_de_alimentos` continuam separadas e sem tradução: respectivamente 9 e 15 linhas de itens no geral. Categoria nula não foi excluída nem tratada como tradução conhecida.

Os pagamentos foram analisados por mês de compra, método e status. O método real `not_defined` permanece com três registros, todos de pedidos `canceled`, somando 0,00. Não foi convertido em membro técnico. Não houve atribuição de pagamentos a produtos ou vendedores.

As análises por UF e cidade usam a localização do registro de cliente associado a cada pedido. No geral, SP tem 41.746 pedidos, RJ 12.852 e MG 11.635. Os totais completos por UF e por UF/cidade reproduzem os totais dos respectivos processos. Nenhum endereço foi atribuído permanentemente à identidade analítica; nenhuma consulta usou geolocalização bruta. As grafias originais continuam distintas.

## Clientes e RN07

Foram observadas **96.096 identidades**, iguais à quantidade de membros regulares de `dim_clientes`; 2.997 têm múltiplos pedidos de qualquer status. Ter dois pedidos não basta para RN07: 2.801 identidades têm pelo menos dois pedidos `delivered`, mas somente **2.015** possuem entregues em pelo menos dois dias civis de compra distintos. As outras **786** não satisfazem o requisito de dias distintos.

O denominador desta proporção descritiva é **93.358 identidades conhecidas com pelo menos um pedido `delivered` em dia de compra informado**. O numerador é o subconjunto de 2.015 identidades com pelo menos dois dias elegíveis. A divisão resulta em **2,1583581482036890%**. Não é uma taxa de retenção por coorte, não pressupõe compras independentes e não estabelece um KPI adicional. A escolha de população e janela para um indicador de negócio futuro permanece sujeita a decisão.

Não há pedidos com identidade técnica, localização técnica ou data de compra ausente nesta versão; assim, essas condições não retiraram registros do denominador. Um desconhecido nunca é contado como cliente único nem agrupado como comprador recorrente. O arquivo `clientes_pedidos` mantém pedidos, entregues, dias elegíveis e primeira/última compra por identidade, permitindo auditar o critério. Clientes distintos e pedidos distintos em grupos de produto, vendedor ou método não são medidas aditivas entre esses grupos.

## Reconciliação e cardinalidade

As [20 comparações Silver × Gold](etapa5_validacao_analitica/20261108T042110748288Z/validacao_silver_gold.json) usam diferença simétrica com `EXCEPT ALL`, incluindo nulos e valores exatos. Todas retornaram zero diferenças. A Silver resolve os atributos pelos identificadores naturais; a Gold usa as SKs existentes. Foram comparados resumos, status, meses, produtos, categorias, vendedores, métodos, clientes, localidades e reconciliação por pedido em ambos os escopos.

Os joins de cada fato às suas dimensões mantiveram **99.441, 112.650 e 103.886 linhas**, com as mesmas quantidades de grãos distintos e nenhuma FK sem correspondência. As somas de linhas e medidas foram novamente conferidas entre resumos e agrupamentos. Não se somaram pedidos distintos de produtos, vendedores ou métodos como se fossem partições exclusivas.

Itens e pagamentos foram agregados **separadamente por pedido** antes da reconciliação. Todos os pedidos permanecem na base por `LEFT JOIN`; ausência de filhos não se torna valor zero e não entra como diferença monetária calculável.

| Reconciliação | Geral | `delivered` |
| --- | ---: | ---: |
| Pedidos sem itens | 775 | 0 |
| Pedidos sem pagamento | 1 | 1 |
| Pedidos comparáveis | 98.665 | 96.477 |
| Diferença absoluta superior a 0,01 | 303 | 299 |
| Pagamentos maiores que itens + frete | 264 | 260 |
| Pagamentos menores que itens + frete | 39 | 39 |

O sinal é `payment_value − price − freight_value`, após agregação independente. A mesma reconciliação fecha por status, mês e UF. O limite de 0,01 é apenas o recorte diagnóstico já existente, não autorização de ajuste nem tolerância de aceite contábil. As divergências não são falhas introduzidas pela Gold e suas causas não foram inferidas.

Os [snapshots](etapa5_validacao_analitica/20261108T042110748288Z/snapshots.json) registram fingerprints integrais de conteúdo Silver, fatos e dimensões e os catálogos, iguais antes e depois na mesma transação. Os nove fingerprints Gold coincidem com a evidência da etapa 4C, incluindo SKs. Os nove SHA-256 Bronze permaneceram iguais. A comparação dos arquivos preexistentes também está registrada, sem alterações. A fotografia transacional não pretende auditar eventuais escritores externos após seu encerramento.

## Reprodução e arquivos

Com a configuração local protegida já existente, executar na raiz:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\executar_validacao_analitica.ps1
```

O executor restaura o ambiente ao terminar e não imprime credenciais. Cada execução gera uma nova pasta de evidências. `scripts/validacao_analitica.py --prepare` apenas prepara as consultas, sem conexão. Os arquivos SQL são consultas de leitura; para reprodução isolada, devem ser executados em transação `READ ONLY` no banco correto. A execução consolidada efetiva, com configuração de sessão e `ROLLBACK`, está em `execucao.sql` nas evidências.

Arquivos criados:

- `sql/validacoes/analitica/01_*.sql` a `24_*.sql`: 17 consultas de agregação por processo, pedidos por cliente, RN07, reconciliação em níveis, comparação Silver × Gold, cardinalidades, datas e denominadores;
- `scripts/validacao_analitica.py` e `scripts/executar_validacao_analitica.ps1`: geração, execução protegida e evidências;
- `tests/test_validacao_analitica.py`: contrato de leitura e precisão decimal;
- este relatório e `docs/qualidade/etapa5_validacao_analitica/`: resultados completos, SQL executado, testes, snapshots e registro da tentativa inicial.

Não houve modificação de documentos aprovados, dependências, fontes ou objetos do banco.

## Limitações e decisões pendentes

Os resultados descrevem a extração estática disponível e os status finais registrados, sem histórico de transições. O início e o fim da cobertura têm meses parciais; evolução mensal não equivale a comparação homogênea de períodos. A proporção RN07 depende da exposição observada de cada cliente e não demonstra fidelização ou independência das compras.

Permanecem pendentes a confirmação de unidade monetária e procedência/licença; investigação das 303 diferenças e dos pedidos sem filhos; significado comercial detalhado de zeros e `not_defined`; tradução das categorias sem correspondência; janelas, coortes e população de eventuais indicadores de negócio. Não há regra aprovada de rateio pagamento–produto/vendedor, nem evidência para concluir recebimento, custo, margem, lucro ou receita contábil. Nenhuma dessas lacunas foi preenchida por hipótese numérica ou correção automática.
