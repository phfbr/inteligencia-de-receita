# Etapa 4B — Dimensões Gold

## Execução e escopo

Foram implementados o schema `gold` e somente as seis dimensões previstas no [modelo dimensional](../modelagem/modelo_dimensional.md), mantendo as [regras RN01–RN08](../regras_negocio/regras.md). A execução ocorreu em 8 de novembro de 2026 no banco exclusivo `inteligencia_receita_db`, PostgreSQL 18.6, com autenticação local protegida. Não foram criados fatos, views, funções persistentes, sequências, DAX ou dashboards.

O [resultado da execução](etapa4_gold_dimensoes/20261108T033107805228Z/resultado.json) registra `completed_verified`, sem erros, com idempotência, rollback e preservação da Bronze e Silver confirmados. As duas cargas receberam `COMMIT`; a terceira provocou a divisão por zero esperada, SQLSTATE `22012`, e foi revertida. Os [resultados da primeira carga](etapa4_gold_dimensoes/20261108T033107805228Z/first.json), [segunda carga](etapa4_gold_dimensoes/20261108T033107805228Z/second.json) e [falha deliberada](etapa4_gold_dimensoes/20261108T033107805228Z/rollback.json) foram preservados separadamente.

A fonte de compatibilidade é a [conferência Silver da Etapa 4A](etapa4_silver/conclusao_20261108T024814481530Z/integracao/verify/resultado.json). Seus hashes, contagens, nulos, valores tipados, somas e fingerprints dos registros foram verificados no banco antes da criação Gold e novamente depois dos testes. Nenhuma tabela Silver foi recarregada ou alterada.

## Confronto com o modelo e decisões físicas

As chaves naturais de produtos, vendedores, registros de cliente e tradução foram verificadas antes do DDL. O agrupamento de vários `customer_id` sob um `customer_unique_id` é o grão declarado de cliente, não uma limpeza da fonte. Não houve conflito de unicidade na versão analisada que exigisse escolha arbitrária de atributos.

As decisões físicas que estavam abertas foram resolvidas da seguinte forma:

| Tema | Decisão e justificativa |
| --- | --- |
| Chaves substitutas | `BIGINT`, com valores regulares positivos atribuídos por `row_number()` sobre as identidades naturais ordenadas. Evita sequências e dependência da ordem física de leitura nesta versão estática |
| Comparação textual | `TEXT COLLATE "C"` nas identidades e atributos textuais, sem alterar caixa, acentos, espaços ou zeros à esquerda |
| Histórico | Sem SCD2, datas de vigência ou versões artificiais; um membro regular por identidade natural |
| Carga idempotente | Inserir as linhas esperadas com conflito apenas na SK tratado como ausência de inserção; comparar depois todo o conjunto, inclusive atributos e SK. Nenhum `DO UPDATE`, descarte ou ajuste silencioso |
| Divergência em dimensão preexistente | Se o conteúdo não coincidir com a versão esperada, a comparação integral falha e a transação é revertida. O carregador não remapeia chaves nem escolhe uma versão de atributo arbitrariamente |
| Cliente | Apenas identidade analítica e classificação de membro. Não há `customer_id`, endereço ou localização permanente na dimensão |
| Localização | Uma linha por tupla exata completa de prefixo de CEP, cidade e UF do registro de cliente associado ao pedido |
| Calendário | Espinha diária contínua do menor ao maior dia dos seis papéis documentados. Mantém dias intermediários para consistência do domínio temporal, sem estender até a data atual |
| Produtos | Atributos originais da Silver e tradução da categoria por relação previamente verificada como única. Produto sem categoria ou tradução continua sendo produto conhecido |
| Métodos | Um membro regular por `payment_type`, incluindo literalmente `not_defined`; parcelamento não pertence a essa dimensão |

`row_number()` retorna `BIGINT` e depende da ordenação informada, conforme a documentação de [funções de janela do PostgreSQL](https://www.postgresql.org/docs/18/functions-window.html). A ordem usa todas as partes da identidade natural, com comparação `C` nos textos; calendário usa a própria data. Não há empates entre identidades regulares após as verificações de unicidade.

O mapeamento é determinístico **para a versão estática fixada**. Não se promete estabilidade das posições ordinais caso novas identidades sejam acrescentadas ou a fonte seja substituída. A Silver é conferida contra a versão de referência antes de cada execução; uma evolução de fonte exige uma política explícita de manutenção de chaves e atributos, fora desta entrega.

## Objetos e atributos

O [catálogo real](etapa4_gold_dimensoes/20261108T033107805228Z/catalogo.json) contém seis tabelas, doze índices associados a PK e UNIQUE, 35 colunas e trinta restrições no PostgreSQL 18. As restrições incluem seis PKs, seis UNIQUE, seis CHECKs de membros e doze NOT NULL de SK/classificação. Os índices não são objetos auxiliares de análise.

| Dimensão | SK | Identidade natural | Demais atributos |
| --- | --- | --- | --- |
| `gold.dim_clientes` | `cliente_sk` | `customer_unique_id` | `membro_tipo` |
| `gold.dim_produtos` | `produto_sk` | `product_id` | Categoria original, categoria em inglês quando encontrada, campos originais de comprimento de nome/descrição, quantidade de fotos, peso e dimensões físicas; `membro_tipo` |
| `gold.dim_vendedores` | `vendedor_sk` | `seller_id` | Prefixo de CEP, cidade e UF originais do vendedor; `membro_tipo` |
| `gold.dim_calendario` | `data_sk` | `dia` | `ano`, `mes`, `dia_mes`; `membro_tipo` |
| `gold.dim_localizacao` | `localizacao_sk` | `customer_zip_code_prefix + customer_city + customer_state` | `membro_tipo` |
| `gold.dim_forma_pagamento` | `forma_pagamento_sk` | `payment_type` | `membro_tipo` |

Identificadores e prefixos de CEP são `TEXT`. Os atributos numéricos de produto permanecem `NUMERIC` exatos; componentes civis são `INTEGER` e o dia é `DATE`. Não foram inventados nomes textuais de produtos a partir dos campos de comprimento, nem rótulos traduzidos para métodos de pagamento.

A resolução de contexto segue `order_id → customer_id → customer_unique_id` para identidade e, separadamente, `order_id → customer_id → CEP/cidade/UF` para localização. As três partes da tupla são comparadas como campos separados, sem concatenação ambígua, normalização, escolha da primeira/última localidade ou associação permanente ao cliente. Os campos do vendedor não substituem o contexto do cliente.

Os valores textuais originais e timestamps completos continuam rastreáveis na Silver, inclusive em `_raw_record`, sem alteração pela carga Gold. As dimensões mantêm os atributos projetados exatamente como tipados na Silver. Para cliente com várias linhas de origem, a rastreabilidade continua disponível pela identidade analítica nos registros Silver, sem escolher um registro representativo ou construir uma ponte persistente nesta etapa.

## Membros especiais

Todas as seis dimensões têm os mesmos dois códigos técnicos, independentes das chaves da origem:

| SK | `membro_tipo` | Uso |
| --- | --- | --- |
| `-1` | `nao_informado` | Chave ausente, componente obrigatório ausente ou data não informada na fonte |
| `-2` | `referencia_nao_encontrada` | Chave preenchida sem correspondência na referência esperada |
| Positiva | `regular` | Identidade natural resolvida, com valores preservados |

As chaves naturais e os demais atributos são `NULL` nos dois membros especiais. Os CHECKs distinguem as duas classes e exigem identidade completa em membros regulares. A unicidade natural usa a semântica padrão de [UNIQUE no PostgreSQL](https://www.postgresql.org/docs/18/ddl-constraints.html): nulos distintos permitem os dois membros técnicos, enquanto as identidades regulares são não nulas por CHECK e únicas por UNIQUE.

Não há membro “não aplicável”: nenhum caso desta entrega tem evidência suficiente para essa classificação. Data vazia não comprova que o evento não ocorreu; status isolado não muda esse entendimento. Um uso futuro de “não aplicável” requer justificativa e revisão explícitas, sem reutilizar `-1` ou `-2`.

O método `not_defined` é um membro **regular**, com SK positiva, e não um sinônimo dos membros técnicos. Identidades desconhecidas não serão tratadas como uma mesma pessoa para futura análise de recompra. Ausência de item ou pagamento não gera registro artificial ou dimensão ligada a uma transação inexistente.

O teste de falha usa somente a exclusão temporária do membro técnico `dim_clientes.cliente_sk = -2`, dentro da transação que recebe `22012`. A verificação posterior exige o conjunto completo novamente, demonstrando a restauração desse membro e dos demais conteúdos. Não foi persistido cadastro fictício.

## Quantitativos calculados

A [inspeção prévia somente leitura](etapa4_gold_dimensoes/20261108T032731182373Z/resultado.json) calculou as identidades antes de criar objetos. A carga compara cada dimensão inteira com a projeção esperada da Silver, incluindo chaves, atributos, multiplicidade e os dois membros especiais. Os totais não foram presumidos a partir das linhas dos CSVs.

| Dimensão | Identidades regulares esperadas | Regulares carregados | Especiais | Total carregado |
| --- | ---: | ---: | ---: | ---: |
| `dim_clientes` | 96.096 | 96.096 | 2 | 96.098 |
| `dim_produtos` | 32.951 | 32.951 | 2 | 32.953 |
| `dim_vendedores` | 3.095 | 3.095 | 2 | 3.097 |
| `dim_calendario` | 1.314 | 1.314 | 2 | 1.316 |
| `dim_localizacao` | 15.034 | 15.034 | 2 | 15.036 |
| `dim_forma_pagamento` | 5 | 5 | 2 | 7 |
| **Total de membros de dimensões diferentes** | **148.495** | **148.495** | **12** | **148.507** |

Cada dimensão contém exatamente um `-1` e um `-2`. O total é controle de carga, não indicador comercial.

### Cobertura do calendário

Foram considerados `order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date` e `shipping_limit_date`. Não foi criada data própria de pagamento/recebimento, e datas de avaliações não foram incorporadas como novos papéis do modelo.

Esses seis campos apresentam **720 dias distintos observados**, de **04/09/2016 a 09/04/2020**. O intervalo contínuo tem **1.314 dias**, dos quais 594 não aparecem diretamente nesses campos. Esses dias intermediários são membros regulares do calendário civil, não eventos inventados. As 1.314 identidades da espinha foram comparadas à dimensão; os 720 dias efetivamente observados também foram resolvidos nos testes por papel.

Nenhum fuso foi inferido ou convertido: usa-se a parte de data dos timestamps sem fuso da Silver. O dia máximo observado foi preservado, sem corte arbitrário pelo período principal dos pedidos. A origem desse extremo continua dependente da investigação da fonte. Os membros `-1` e `-2` têm `dia`, ano, mês e dia do mês nulos; não foi usada data sentinela como 01/01/1900.

## Testes e resoluções reais

Os [dez testes locais](etapa4_gold_dimensoes/testes_locais.log) passaram. Eles verificam escopo dos seis objetos, ausência de endereço permanente no cliente, uso da tupla exata, ordenação determinística, membros distintos, papéis do calendário, limites da adaptação de proteção, correspondência entre gerador e SQL revisado, distinção de `not_defined` e tratamento específico das violações esperadas.

No PostgreSQL foram executadas, antes de cada commit, comparações simétricas com `EXCEPT ALL` entre a dimensão e seu conjunto esperado. Além de contar linhas e identidades, essas comparações verificam todos os atributos e os mapeamentos SK–chave natural. A estrutura física é conferida em catálogo, com ownership, comentários, tipos, nulabilidade, PK, UNIQUE e CHECK esperado.

Os testes físicos tentaram, em blocos transacionais controlados, inserir membro regular sem identidade e duplicar uma identidade natural com outra SK. Foram exigidos respectivamente `check_violation` e `unique_violation`; qualquer outra falha ou aceitação indevida interromperia a carga. Consultas sintéticas também verificaram as saídas `-1` e `-2`, sem persistir identidades artificiais. A versão da fonte não precisou desses casos sintéticos para resolver entidades reais.

Foram verificados **17 caminhos de resolução**, sem aumento de cardinalidade e sem referência não encontrada:

- pedido → cliente e localização;
- item → produto e vendedor;
- item e pagamento → pedido → cliente, localização e dia de compra;
- pagamento → método;
- os seis papéis temporais documentados, em suas fontes correspondentes.

Todos os 99.441 pedidos resolveram cliente e localização regulares; os 112.650 itens resolveram produto e vendedor, além do contexto de pedido; os 103.886 pagamentos resolveram método e contexto. Nas datas, houve os seguintes usos legítimos de “não informado”:

| Papel | Registros sem data |
| --- | ---: |
| Aprovação | 160 |
| Entrega à transportadora | 1.783 |
| Entrega ao cliente | 2.965 |
| Compra, previsão de entrega e limite de envio | 0 |

São 4.908 ausências em papéis distintos, não 4.908 membros de calendário nem necessariamente pedidos distintos. Todas as datas preenchidas resolveram membros regulares. Não houve tupla parcial de localização entre os pedidos examinados; a regra futura para componente obrigatório ausente continua sendo `-1`, preservando os componentes disponíveis na Silver.

Os fingerprints ordenados de todas as dimensões foram idênticos entre a primeira carga, a segunda e a conferência pós-rollback. Não houve erro inesperado. A única falha da execução foi a divisão por zero deliberada, registrada como `expected_failure`, exigida para provar a reversão.

## Exceções preservadas e proteção da Silver

Os 610 produtos sem categoria e os 13 com categoria sem tradução continuam membros regulares, sem categoria ou tradução inventada. O vínculo de tradução permanece opcional; não foi criada dimensão de categoria. A categoria original foi preservada nesses casos.

A verificação integral pós-Gold confirmou as nove tabelas Silver e seus **1.550.922 registros**, incluindo geolocalização e avaliações sem deduplicação. Permanecem as 303 diferenças monetárias superiores a 0,01 entre pagamentos e itens mais frete, sendo 264 positivas e 39 negativas. Não houve correção, rateio ou filtro comercial aplicado para construir dimensões. RN02 não foi usado como filtro da identidade de clientes, produtos ou localidades; RN07 não foi implementada como métrica.

O arquivo geográfico bruto participou somente da conferência de preservação da Silver. Não há join de construção ou resolução dimensional com essa fonte. A Bronze também manteve os nove SHA-256 da versão de referência.

## Transação, isolamento e compatibilidade operacional

O destino, ownership, marcador do projeto, schemas, objetos permitidos e compatibilidade integral da Silver são conferidos antes do primeiro DDL. Um schema Gold preexistente sem identificação ou uma tabela incompatível provoca recusa, sem remoção ou adoção automática. O schema e as tabelas desta entrega recebem comentários próprios de identificação.

A carga usa uma transação por execução, isolamento `REPEATABLE READ`, lock consultivo do projeto e locks `SHARE` nas nove tabelas Silver. Esses locks impedem mudança de fonte durante a construção, sem escrever na Silver. Uma nova inspeção e todos os testes precedem o commit. Não há `DROP`, `TRUNCATE`, atualização automática de atributos ou exclusão na carga regular. O teste de rollback é a única exclusão Gold e foi revertida.

A proteção da etapa 4A tinha uma allowlist limitada a `public` e `silver`. Para preservar os arquivos validados, a etapa 4B adapta essa allowlist **localmente**, acrescentando somente `gold`, as seis tabelas e seus doze índices esperados. As demais verificações Silver continuam as mesmas. Não foi desativada a proteção, nem ampliada a permissão para objetos arbitrários.

Consequentemente, os executores originais da Silver, sem essa adaptação, continuam recusando um destino que contenha Gold. Para conferir a fonte nesta etapa, usa-se o executor Gold em modo de inspeção, que valida a Silver em somente leitura. Uma futura recarga Silver com Gold já existente exige compatibilização explícita das ferramentas e revalidação dos consumidores; não se deve remover a proteção antiga para forçar a operação. Isso é uma limitação operacional da separação das etapas, não mudança do modelo dimensional.

## Reprodução e arquivos

Não há dependências Python adicionais, alterações de serviços ou senhas em arquivos versionados. O wrapper reutiliza a configuração local protegida já existente e restaura o ambiente do processo ao terminar.

```text
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\executar_gold_dimensoes.ps1 -Mode inspect
python -m unittest discover -s tests -p test_gold_dimensoes.py -v
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\executar_gold_dimensoes.ps1 -Mode run
```

O comando `python` pressupõe um interpretador funcional; o wrapper usa a instalação local já verificada. `inspect` valida o destino e a Silver e calcula as chaves naturais sem criar objetos. `run` executa carga, reexecução, testes físicos e rollback. Cada execução grava evidências em uma pasta nova com horário UTC; os resultados anteriores não são sobrescritos.

Arquivos de implementação: [gold_dimensoes.py](../../scripts/gold_dimensoes.py), [executar_gold_dimensoes.ps1](../../scripts/executar_gold_dimensoes.ps1), [DDL](../../sql/gold/001_dimensoes.sql), [carga](../../sql/gold/002_carga_dimensoes.sql), [validações](../../sql/validacoes/gold_dimensoes.sql) e [testes locais](../../tests/test_gold_dimensoes.py). Os blocos de testes físicos e a falha deliberada são gerados pelo executor, sem objetos auxiliares persistentes.

O [catálogo](etapa4_gold_dimensoes/20261108T033107805228Z/catalogo.json), os fingerprints e a [conferência final](etapa4_gold_dimensoes/20261108T033107805228Z/verificacoes_finais.json) registram os objetos e a cadeia de preservação dos artefatos e fontes. O modelo, as regras, os executores e SQL da Silver, suas evidências e os CSVs foram preservados.

## Pendências e limites

Permanecem pendentes a procedência externa/licença da cópia, explicação das exceções de categoria e datas, e política de evolução de identidades e atributos para versões futuras. Não há evidência para fundir grafias geográficas distintas, inferir localização permanente, criar histórico ou transformar `not_defined` em ausência técnica.

A manutenção das chaves diante de novas fontes e a compatibilização de uma futura recarga Silver com Gold precisam de decisão própria. Os fatos e seus relacionamentos físicos não fazem parte desta entrega; a resolução foi testada por consultas, sem materializar fatos ou pontes. Não há definição de indicadores finais ou consumo em Power BI.

A Etapa 4B não está declarada aprovada.
