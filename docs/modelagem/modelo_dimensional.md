# Especificação lógica do Data Warehouse

## Objetivo e condição desta especificação

Esta proposta organiza a análise comercial e financeira em três fatos de grãos distintos, seguindo a abordagem Kimball: explicitar o processo e o grão antes de associar dimensões e medidas. O desenho incorpora as decisões RN01–RN08, documentadas preliminarmente em [regras.md](../regras_negocio/regras.md), e não constitui aprovação da modelagem ou implementação física.

As bases de comparação são o [profiling](../qualidade/profiling/resultados.json), o [relatório de qualidade](../qualidade/etapa2_profiling.md), o [diagnóstico](../regras_negocio/diagnostico.md) e seus [resultados estruturados](../regras_negocio/evidencias/diagnostico.json). Todas as contagens citadas descrevem a cópia local já analisada; não são previsões de carga nem garantias para futuras versões.

Na consolidação da versão estática, ficam definidos: chaves naturais nos fatos e substitutas nas dimensões; ausência de SCD2; localização pela combinação exata dos componentes originais do cliente associado ao pedido; calendário pelo dia civil da fonte; recompra observada por pedidos `delivered` em dias de compra distintos; categorias separadas de membros especiais; valores monetários em `NUMERIC` exato. Essas decisões substituem as alternativas antes pendentes nesses pontos, preservando as evidências e as demais ressalvas.

## Confronto prévio entre o desenho e as evidências

| Evidência observada | Consequência para o modelo | Conflito ou decisão ainda aberta |
| --- | --- | --- |
| 99.441 pedidos; 775 sem itens e um sem pagamento, este último `delivered` | `fato_pedidos` independe da existência de filhos; os outros fatos não recebem linhas artificiais | Diferenciar ausência de registro de valor zero; não restringir a preservação aos pedidos completos |
| 112.650 combinações únicas de pedido/item e 103.886 de pedido/sequência de pagamento | Os grãos propostos de itens e pagamentos são compatíveis com a cópia analisada | Unicidade não determina por si só a semântica de quantidade ou parcela |
| 275 pedidos com múltiplos itens e múltiplos pagamentos; junção direta produziria 117.601 linhas | Fatos separados; comparação após agregação independente ao grão comum | Não existe relação observada pagamento–item ou pagamento–vendedor; rateios não foram definidos |
| 96.096 `customer_unique_id` em 99.441 linhas de clientes; 2.997 com múltiplos pedidos | A dimensão de clientes usa identidade analítica única; `customer_id` mantém função de rastreabilidade do contexto de origem | Atributos do cliente não podem ser escolhidos arbitrariamente entre seus registros, especialmente localização |
| 290 clientes com compras no mesmo segundo; 2.801 com ao menos dois pedidos entregues | RN07 exige ao menos dois `delivered` em dias de compra distintos, conforme o dia civil registrado na fonte | O cruzamento final não foi recalculado nesta entrega; as 2.801 ocorrências não comprovam a condição completa nem independência das compras |
| Oito entregues sem data de entrega; seis cancelados com data de entrega ao cliente | Status e datas são preservados separadamente; RN02 usa `delivered`, sem substituir o status pelas datas | Ausência de data não autoriza excluir um entregue; datas incoerentes continuam como sinal de qualidade |
| 303 diferenças superiores a 0,01 entre pagamentos e itens mais frete: 299 entregues | Valores originais e diferenças permanecem rastreáveis; RN05 independe de RN02 | Causa e tolerância financeira continuam sem definição; não ajustar valores para reconciliar |
| Geolocalização: 1.000.163 linhas, 261.831 duplicatas exatas excedentes, 19.015 prefixos de CEP distintos | RN08 impede a junção à fonte bruta; a localização usa a tupla exata de CEP/cidade/UF do cliente ligado ao pedido | Grafias diferentes continuam diferentes; equivalência geográfica e coordenadas não foram comprovadas nem escolhidas |
| 610 produtos sem categoria e 13 em duas categorias sem tradução | Produto conhecido não se torna desconhecido apenas por atributo ausente ou tradução não encontrada | Tratamento de atributos e tradução deve preservar categoria original, sem inventar correspondência |
| Métodos de pagamento incluem três `not_defined`; há nove valores zero | A dimensão representa o método registrado, e o fato conserva zeros | `not_defined` não deve ser confundido silenciosamente com falha técnica de referência |

Não foi identificada incompatibilidade de unicidade com os três grãos propostos. Permanecem incompatíveis com as evidências as interpretações de localização permanente do cliente, pagamento como recebimento e soma de fatos unidos em suas linhas originais.

## Processos, grãos e chaves dos fatos

Os fatos usam as chaves naturais abaixo como identificadores de suas linhas, sem chave substituta factual nesta versão. As referências às dimensões usam chaves substitutas. Os tipos físicos candidatos são documentados adiante, sem geração de sequências, índices ou DDL.

| Fato | Processo e grão declarado | Chave natural definida | Chave substituta factual | Conteúdo e limites |
| --- | --- | --- | --- | --- |
| `fato_pedidos` | Uma linha por pedido da origem, com seu estado disponível na extração | `order_id` | Não adotada | Preserva todos os status, datas originais e referências do contexto; não é histórico de eventos nem fotografia periódica |
| `fato_itens_pedido` | Uma linha por ocorrência de item identificada dentro do pedido | `order_id + order_item_id` | Não adotada | Guarda produto, vendedor, preço, frete e limite de envio daquela ocorrência; não agrega itens iguais |
| `fato_pagamentos` | Uma linha por registro de pagamento identificado por sequência dentro do pedido | `order_id + payment_sequential` | Não adotada | Guarda método, valor e número de parcelas registrado; a sequência não é uma parcela de recebimento |

O pedido é um processo com datas por papel e status observado. Um eventual desenho físico como snapshot acumulativo, assim como sua atualização, exige decisão futura sobre cargas e histórico; não se deduz uma sequência de eventos a partir de uma única extração. Nenhuma linha de item ou pagamento será criada para preencher ausência de filhos. Uma duplicidade futura de chave deve ser sinalizada e investigada, sem deduplicação silenciosa.

### Dimensão degenerada do pedido

`order_id` é a dimensão degenerada compartilhada pelos três fatos: identifica o documento transacional e permite rastreabilidade e reconciliação. Não exige uma `dim_pedidos`. Seu valor não autoriza um relacionamento analítico muitos-para-muitos entre os fatos. `order_item_id` e `payment_sequential` são identificadores locais do respectivo grão, não medidas somáveis.

## Dimensões propostas

| Dimensão | Grão lógico | Identidade natural definida | Chave substituta definida | Atributos candidatos e origem |
| --- | --- | --- | --- | --- |
| `dim_clientes` | Uma identidade analítica por `customer_unique_id`, sem versões SCD2 | `customer_unique_id` | `cliente_sk` | Identificador anonimizado; não há atributos demográficos disponíveis comprovados. O vínculo com os diversos `customer_id` deve permanecer rastreável, sem criar uma linha dimensional por `customer_id` |
| `dim_produtos` | Um produto da origem, sem versões SCD2 | `product_id` | `produto_sk` | Categoria original, tradução quando encontrada, campos de comprimento de nome/descrição, fotos, peso e dimensões físicas. Não há nome ou descrição textual do produto comprovados nesses campos de comprimento |
| `dim_vendedores` | Um vendedor da origem, sem versões SCD2 | `seller_id` | `vendedor_sk` | Prefixo de CEP, cidade e estado registrados no arquivo de vendedores; não representam a localização do cliente |
| `dim_calendario` | Um dia civil da fonte por membro regular, além dos membros especiais | Data completa do dia | `data_sk`, substituta independente da data | Ano, mês, dia e demais atributos civis determinísticos; calendário fiscal, feriados e convenção de semana permanecem pendentes |
| `dim_localizacao` | Uma combinação exata de localidade observada no registro de cliente associado ao pedido | Tupla exata de `customer_zip_code_prefix`, `customer_city` e `customer_state` | `localizacao_sk` | Componentes originais de CEP/cidade/UF preservados; sem endereço completo, coordenada escolhida ou localização permanente da identidade analítica |
| `dim_forma_pagamento` | Um método de pagamento registrado na origem | `payment_type` | `forma_pagamento_sk` | Código original; rótulo descritivo apenas quando documentado. Parcelamento pertence ao registro de pagamento, não define o grão desta dimensão |

O caminho para resolver cliente e local do pedido é `orders.customer_id → customers.customer_id`. Desse registro, `customer_unique_id` resolve a identidade analítica e os campos geográficos resolvem o contexto de localização. Não haverá relação que escolha uma única localização definitiva para cada `customer_unique_id`. Esse caminho não comprova endereço efetivo de entrega: a localização é a informada no registro de cliente vinculado ao pedido.

Se um cliente tiver pedidos com localidades diferentes, cada fato recebe o contexto do seu pedido. Itens e pagamentos podem herdar esse mesmo contexto de forma unívoca por `order_id`. Não se escolherá a primeira ou última localidade para preencher todos os pedidos da identidade.

A identidade de localização é a combinação exata dos três componentes textuais, comparados separadamente, sem concatenação ambígua, remoção de espaços, alteração de caixa, acentos ou normalização. Tuplas idênticas resolvem o mesmo membro; qualquer componente diferente identifica outra combinação. Preservam-se os componentes originais, inclusive zeros à esquerda do prefixo de CEP. Uma equivalência textual não comprova equivalência geográfica. Não há junção à geolocalização bruta, mesclagem de grafias ou escolha de latitude/longitude. A quantidade de membros e as propriedades da comparação textual no ambiente físico precisam ser verificadas antes da implementação.

### Histórico e conformidade

Clientes, produtos e vendedores têm identificadores naturais preenchidos e os dois últimos são únicos em seus arquivos atuais. Isso não fornece datas de vigência nem comprova histórico de atributos. A versão estática não usa SCD2: há um membro regular por identidade natural, sem intervalos de vigência, versões artificiais ou reconstrução retroativa. A atribuição de uma chave substituta não cria histórico. Política de atualização ou sobrescrita de atributos em futuras versões exigirá decisão própria; esta especificação não autoriza atualizações automáticas. Novos extratos não serão tratados como eventos históricos comprovados apenas por chegarem depois.

`dim_clientes`, `dim_calendario` e `dim_localizacao` serão conformadas entre os fatos em que aparecem: mesma identidade, domínio, significado e regra de resolução. Papéis diferentes do calendário reutilizam os mesmos membros. Produtos e vendedores ficam no contexto dos itens; forma de pagamento, no contexto dos pagamentos. Reutilização futura dessas dimensões exige manter seus significados, sem adicionar relações não observadas nesta proposta.

## Matriz fato–dimensão

“Contexto do pedido” indica informação herdada por um vínculo único validado, não uma associação multiplicadora entre fatos. A matriz é lógica; não define relacionamentos de ferramenta de BI.

| Fato | Clientes | Produtos | Vendedores | Calendário | Localização do cliente no pedido | Forma de pagamento |
| --- | --- | --- | --- | --- | --- | --- |
| `fato_pedidos` | Sim, pelo registro de cliente do pedido | Não; um pedido pode ter vários produtos | Não; um pedido pode ter vários vendedores | Compra, aprovação, transportadora, entrega e previsão | Sim | Não; um pedido pode ter vários métodos |
| `fato_itens_pedido` | Sim, contexto do pedido | Sim | Sim | Compra por contexto do pedido; limite de envio do item | Sim, contexto do pedido | Não há vínculo observado item–método |
| `fato_pagamentos` | Sim, contexto do pedido | Não há vínculo observado pagamento–produto | Não há vínculo observado pagamento–vendedor | Compra por contexto do pedido; sem data própria de pagamento comprovada | Sim, contexto do pedido | Sim |

Não há dimensão de status adicional nesta proposta. O status original é atributo contextual do pedido; eventual disponibilização nos fatos filhos deve usar o mesmo valor e a mesma referência de extração, sem redefinir o grão ou criar históricos independentes.

### Matriz das relações dimensionais 1:N

Cada célula preenchida representa dimensão no lado 1 e fato no lado N, fisicamente referenciado pela chave substituta indicada. Um membro pode aparecer em zero ou muitas linhas; cada linha do fato resolve exatamente um membro por relação aplicável, regular ou especial. “—” significa que a relação não existe neste desenho, sem criar coluna ou associação artificial.

| Dimensão no lado 1 | `fato_pedidos` no lado N | `fato_itens_pedido` no lado N | `fato_pagamentos` no lado N |
| --- | --- | --- | --- |
| `dim_clientes` | 1:N por `cliente_sk` | 1:N por `cliente_sk`, contexto do pedido | 1:N por `cliente_sk`, contexto do pedido |
| `dim_produtos` | — | 1:N por `produto_sk` | — |
| `dim_vendedores` | — | 1:N por `vendedor_sk` | — |
| `dim_localizacao` | 1:N por `localizacao_sk` | 1:N por `localizacao_sk`, contexto do pedido | 1:N por `localizacao_sk`, contexto do pedido |
| `dim_forma_pagamento` | — | — | 1:N por `forma_pagamento_sk` |
| `dim_calendario` | Uma relação 1:N por papel: compra, aprovação, transportadora, entrega e previsão | Uma relação 1:N por papel: compra e limite de envio | 1:N no papel compra, sem papel de recebimento |

A repetição do contexto de pedido nos filhos é resolução dimensional, não relacionamento muitos-para-muitos entre fatos. O pedido continua identificado por sua chave natural e dimensão degenerada `order_id`.

## Cardinalidades e navegação entre processos

| Relação | Cardinalidade lógica | Evidência ou ressalva |
| --- | --- | --- |
| Cliente → pedidos | 1 para 0..N; cada pedido resolve um cliente ou membro especial | 96.096 identidades para 99.441 pedidos; até 17 pedidos por identidade nesta cópia |
| Pedido → itens | 1 para 0..N | Zero a 21 itens; 775 pedidos sem itens |
| Pedido → pagamentos | 1 para 0..N | Zero a 29 registros; um pedido sem pagamento |
| Produto/vendedor → itens | 1 para 0..N; cada item tem um produto e um vendedor ou membro especial | Nenhum órfão observado nos vínculos com produtos e vendedores |
| Método → pagamentos | 1 para 0..N; cada pagamento aponta a um método ou membro especial | Cinco métodos observados, incluindo `not_defined` |
| Localização → linhas dos fatos | 1 para 0..N; cada linha resolve um contexto do pedido | Um membro por tupla exata de CEP/cidade/UF, sem junção à geolocalização bruta; a resolução deve ser verificada |
| Dia por papel → linhas dos fatos | 1 para 0..N; cada papel resolve um dia ou membro especial | Papéis são independentes; datas ausentes não removem o pedido |

As relações entre pedidos e filhos descrevem a origem e a integridade, não recomendam somar valores após unir as três tabelas fato. Na camada analítica, cada processo deve ser agregado independentemente às dimensões conformadas e ao mesmo recorte antes de comparar resultados. Para reconciliação transacional, o grão comum é o pedido, preservando os sem correspondência.

Não há correspondência de pagamento com produto ou vendedor dentro de um pedido com vários itens. Portanto, receita financeira por produto, vendedor ou combinação produto–método não pode ser derivada por cruzamento de linhas. Um eventual rateio exige regra própria, ainda inexistente. Contagem de pedidos por produto ou método é distinta e não pode ser somada entre categorias sobrepostas.

## Datas por papel

O calendário usa o dia civil tal como registrado na fonte: a data extraída de cada timestamp, sem conversão de fuso, deslocamento de horas ou horário de corte alternativo. Não se infere UTC nem fuso brasileiro. O grão diário não substitui os timestamps originais: horas, minutos, segundos e qualquer precisão fracionária existente precisam ser preservados. A representação tipada candidata é `TIMESTAMP WITHOUT TIME ZONE`, mantendo também o texto original rastreável. Não se adiciona offset inexistente, não se trunca o valor original ao dia e não se arredondam frações para caber em precisão insuficiente. Valores ausentes ou inválidos ficam sinalizados; nunca recebem data presumida.

| Campo de origem | Papel lógico | Fato de referência | Observação |
| --- | --- | --- | --- |
| `order_purchase_timestamp` | Data de compra, referência de RN07 | Pedidos; contexto em itens e pagamentos | Dia civil da compra conforme a fonte; não equivale a data de recebimento |
| `order_approved_at` | Data de aprovação | Pedidos | Pode estar ausente; não substitui compra |
| `order_delivered_carrier_date` | Data de entrega à transportadora | Pedidos | Preservar ausência e incoerências cronológicas |
| `order_delivered_customer_date` | Data de entrega ao cliente | Pedidos | Oito entregues sem essa data; não usá-la para reclassificar RN02 |
| `order_estimated_delivery_date` | Data prevista de entrega | Pedidos | Planejamento, não realização |
| `shipping_limit_date` | Data-limite de envio do item | Itens | É específica do item; não escolher arbitrariamente um valor para o pedido |
| Data de pagamento/recebimento | Não disponível como campo próprio comprovado | Nenhum papel de evento financeiro definido | Usar compra como contexto não cria data de pagamento |

A exposição adicional de datas do pedido nos fatos filhos além da compra é uma escolha futura de conveniência, que deve manter o significado por papel. Nunca se preencherá data ausente com compra, previsão ou data de carga para aparentar ocorrência do evento.

Os nomes lógicos candidatos das referências são `data_compra_sk`, `data_aprovacao_sk`, `data_transportadora_sk`, `data_entrega_sk`, `data_previsao_entrega_sk` e `data_limite_envio_sk`, conforme o papel aplicável a cada fato. Todos referenciam `dim_calendario.data_sk`. O timestamp original e sua chave de dia têm funções distintas; a ausência do primeiro resolve um membro especial, sem inventar uma data regular.

## Medidas candidatas e aditividade

As medidas abaixo descrevem o que cada grão suporta. Não constituem catálogo de indicadores finais, definição contábil ou implementação de cálculo. Valores monetários e diferenças usam `NUMERIC` exato, sem passagem intermediária por tipos aproximados. Moeda, limites de precisão/escala e eventual conversão monetária dependem de evidência; nenhuma correção automática é permitida.

| Fato/contexto | Medida ou atributo candidato | Aditividade e restrições |
| --- | --- | --- |
| Pedidos | Contagem de linha de pedido, conceitualmente 1 | Aditiva em partições disjuntas de pedidos, sob um mesmo papel de data; não aditiva entre recortes sobrepostos de produtos ou métodos |
| Pedidos | Status original e sinal de elegibilidade `status = delivered` | Atributos de classificação, não valores monetários; somar o sinal pode contar elegíveis apenas no grão correto e não define um indicador publicado |
| Itens | `price` | Aditivo entre ocorrências de itens no mesmo contexto monetário; não é margem, receita líquida nem valor de pagamento |
| Itens | `freight_value` | Aditivo no grão dos itens e separado de `price`; não inferir custo logístico |
| Itens | Contagem de ocorrência de item, conceitualmente 1 | Aditiva como contagem de linhas; não assumir quantidade física contratada ou usar `order_item_id` como quantidade |
| Pagamentos | `payment_value` | Aditivo entre registros de pagamento sob o mesmo contexto monetário; não representa caixa ou liquidação |
| Pagamentos | Contagem de registro, conceitualmente 1 | Aditiva no grão do registro, não como número de pedidos ou parcelas recebidas |
| Pagamentos | `payment_installments` | Atributo numérico não aditivo para interpretação comercial; não multiplicar `payment_value` nem somar como parcelas efetivamente recebidas |
| Pedido, após agregação independente | Totais observados de preço, frete e pagamentos; diferença de reconciliação | Candidatos derivados no grão do pedido; não replicar por item, método ou vendedor. Diferença só se define com ambas as fontes; somá-la exige mesmo universo, unidade e interpretação explícita |
| Cliente/pedido em qualquer fato | Contagem distinta de clientes ou pedidos | Não aditiva entre períodos, produtos, vendedores ou métodos com sobreposição |
| Datas do pedido | Durações entre eventos | Não aditivas como desempenho; preservar negativos e ausentes como diagnósticos, sem correção automática |

Não há medidas de saldo ou estoque propostas e, portanto, não há medida semiaditiva desse tipo especificada. Nenhum total de pedido será obtido somando novamente totais já repetidos nos fatos filhos. Se totais derivados forem disponibilizados em `fato_pedidos`, sua persistência ou cálculo posterior permanece em aberto; não são valores existentes no CSV de pedidos.

## Campos derivados e rastreabilidade

| Campo lógico candidato | Origem ou expressão conceitual | Condição de uso |
| --- | --- | --- |
| Cliente do fato | `customer_id` do pedido → registro de clientes → `customer_unique_id` | Preservar `customer_id` de origem para auditoria, sem tratá-lo como identidade recorrente |
| Localização do pedido | Componentes do registro de cliente vinculado por `customer_id` | Não herdar uma localização permanente de `customer_unique_id` |
| Elegibilidade comercial | Status observado igual a `delivered` | RN02; não altera a preservação exigida por RN01 |
| Presença e contagem de itens/pagamentos | Existência e número de filhos agregados por pedido | Ausência pode ser contada como zero registros; isso não prova valor monetário zero |
| Preço e frete agregados | Somas separadas de `price` e `freight_value` por pedido | Só depois de preservar o grão dos itens; RN03 |
| Pagamento agregado | Soma de `payment_value` por pedido | RN04; sem converter em recebimentos |
| Diferença assinada | Pagamento agregado − (preço agregado + frete agregado) | RN05, apenas quando comparável; ausência de fonte é “não comparável”, não diferença zero |
| Sinais de qualidade | Datas ausentes, sequência temporal incoerente, valor divergente ou referência não resolvida | Devem acompanhar o valor original; não provocam exclusão ou alteração automática |
| Dia civil por papel | Parte de data do timestamp correspondente tal como informado na fonte | Não perder o timestamp nem inferir ou converter fuso |
| Recompra observada | Pelo menos dois `order_id` distintos com status `delivered` para o mesmo `customer_unique_id`, em dias civis de compra distintos | RN07, na cobertura disponível da fonte; não comprova independência das compras nem define taxa ou horizonte adicional |
| Ordem de compra elegível | Ordenação dos pedidos `delivered` pelo timestamp de compra, sem transformar desempates em precedência real | A atribuição de rótulos por pedido quando há várias compras no mesmo dia continua pendente |

Limites exploratórios, como diferença superior a 0,01 ou proximidade de 60 segundos, pertencem às evidências diagnósticas. Não se tornam tolerância financeira ou sessão de compra por constarem neste documento.

## Membros desconhecidos, ausentes e não aplicáveis

Uma futura implementação deverá manter a linha factual quando faltar referência dimensional, preservando o identificador original e a razão da não resolução. Os códigos físicos dos membros especiais ainda não estão definidos. Distinguem-se os seguintes casos lógicos:

| Situação | Estratégia preliminar | Limite ou pendência |
| --- | --- | --- |
| Chave ou componente obrigatório ausente na origem | Membro especial “não informado” da dimensão aplicável | Preservar componentes parciais e identificadores de origem; não fabricar uma identidade completa, inclusive para localização |
| Chave natural preenchida sem referência encontrada | Membro especial distinto “referência não encontrada” | Preservar a chave procurada e o motivo; não confundir com campo vazio nem fundir identidades em análises de clientes. Membros inferidos por identidade e resolução tardia exigem decisão futura |
| Chave ou valor informado mas inválido para interpretação | Sinal de qualidade específico e valor original preservado; motivo distinto dos anteriores | A classificação técnica de invalidez depende de critério comprovado e não deve ser escondida como ausência. Não descartar o fato nem inventar referência |
| Evento sem data registrada | Membro de calendário para “data não informada/evento não comprovado”, preservando o status e o campo vazio | Não assumir “não ocorreu” apenas porque a data está vazia; distinguir “não aplicável” somente com regra justificável |
| Papel ou atributo existente, mas comprovadamente não aplicável ao registro | Membro ou classificação “não aplicável”, distinto de “não informado” e “referência não encontrada” | Exige justificativa por regra e evidência; nenhum status isolado autoriza presumir essa condição para uma data vazia |
| Produto conhecido sem categoria/tradução | Manter o produto e o texto original; indicar atributo não informado ou tradução não encontrada | Não substituir o produto inteiro por desconhecido nem inventar tradução |
| Método original `not_defined` | Manter código explícito da origem na dimensão | Não equiparar automaticamente a membro técnico de chave desconhecida |
| Pedido sem item ou pagamento | Preservar somente a linha de pedido e registrar ausência dos filhos | Não criar item ou pagamento fictício, nem usar membro desconhecido para simular uma transação ausente |
| Dimensão sem relação no grão, como método em pedidos ou produto em pagamentos | Não criar a chave na matriz atual | Não usar “não aplicável” para disfarçar uma associação muitos-para-muitos inexistente |

A integridade observada dos vínculos não dispensa essa estratégia para futuras cargas. Regras de chegada tardia, remapeamento e auditoria precisam ser definidas antes da implementação, sem alterar a Bronze.

As categorias especiais devem ter chaves substitutas próprias e descrição da razão, sem usar uma única categoria genérica para situações diferentes. Não se atribui dia civil fictício aos membros especiais do calendário. Clientes não resolvidos não serão agrupados como se constituíssem uma mesma identidade para RN07. Nenhuma ausência de filho cria linha factual especial.

## Tipos físicos candidatos, sem DDL

Os tipos abaixo orientam uma implementação posterior; não criam tabelas ou restrições. As decisões sobre chaves, exatidão monetária e ausência de fuso estão formalizadas; tamanhos, limites e política de rejeição técnica dependem das verificações indicadas.

| Campo ou domínio | Tipo candidato | Preservação e pontos dependentes de evidência |
| --- | --- | --- |
| Chaves substitutas dimensionais e referências nos fatos | `BIGINT` | Tipos compatíveis nos dois lados; códigos e geração de membros regulares/especiais ainda a definir |
| IDs naturais textuais: `order_id`, `customer_id`, `customer_unique_id`, `product_id`, `seller_id` | `TEXT` | Preservar exatamente o identificador; não assumir semântica UUID, tamanho fixo ou alterar caixa |
| Componentes naturais `order_item_id` e `payment_sequential` | `TEXT` para preservação literal; representação adicional `INTEGER` candidata | Conversão numérica só após validar faixa e ausência de colisões entre representações distintas; não mudar a identidade da chave composta nem tratar sequência como medida |
| Prefixo de CEP, cidade, UF, categoria, status e método | `TEXT` | Prefixo de CEP continua texto; igualdade da tupla de localização deve respeitar todos os componentes sem normalização ou comparação insensível a caixa/acentos |
| Dia regular de `dim_calendario` | `DATE` | Dia civil da fonte, separado de `data_sk`; membros especiais não recebem datas inventadas |
| Timestamps de origem por papel | `TIMESTAMP WITHOUT TIME ZONE`, com precisão suficiente, e texto original rastreável em `TEXT` | Verificar precisão fracionária e domínio suportado antes de escolher limite; se não representável sem perda, preservar texto e sinalizar, sem arredondamento ou truncamento |
| `price`, `freight_value`, `payment_value`, somas e diferenças | `NUMERIC`, sem restrição de precisão/escala nesta especificação | `NUMERIC(p,s)` somente após comprovar limites de entradas e agregados e impedir arredondamento por coerção; não usar `REAL`, `DOUBLE PRECISION` ou correções para reconciliar |
| Número de parcelas, contagens de atributos e componentes civis | `INTEGER`; agregados de contagem em `BIGINT` | Validar domínio sem descartar zeros observados; parcelas não representam recebimentos |
| Peso e dimensões físicas de produto | `NUMERIC` candidato | Unidade, escala e limites precisam de confirmação; não converter campos ausentes em zero |
| Presença, elegibilidade e sinais de qualidade | `BOOLEAN` ou classificação textual quando houver mais de dois estados | Distinguir falso, ausência e não comparável conforme o significado; não reduzir três causas de membro especial a uma flag única |

`NUMERIC` garante representação decimal, mas não resolve o significado contábil. Valores negativos, zeros e divergências observados permanecem dados, e não gatilhos para correção automática. Durações, quando especificadas fisicamente, deverão preservar sinal e unidade; tipo e precisão ficam pendentes.

## Decisões ainda abertas

- Confirmar procedência, versão, licença, moeda e semântica dos campos da fonte.
- Verificar quantidade de tuplas exatas de localização, componentes ausentes e semântica de comparação física, sem normalizar ou inferir equivalência geográfica.
- Definir geração e códigos das chaves substitutas dimensionais, classificação técnica de inválidos e resolução tardia; a versão estática está definida sem SCD2 e os fatos usam chaves naturais.
- Validar a execução futura de RN07 sobre dias civis de compra e pedidos `delivered`; o cruzamento não foi recalculado nesta entrega. Rótulos por pedido, cortes adicionais de observação e futuras alterações da regra exigem especificação própria, sem inferir independência das compras.
- Confirmar faixas e precisão dos tipos candidatos, inclusive timestamps e eventual `NUMERIC(p,s)`, sem aceitar perdas ou arredondamentos silenciosos.
- Investigar ausências e divergências sem ajustar valores ou presumir recebimentos; o limiar exploratório não é tolerância aprovada.
- Decidir disponibilização de status e datas contextuais nos filhos e persistência de derivados do pedido, preservando os três grãos.
- Documentar eventual necessidade de rateio antes de relacionar pagamentos a produto ou vendedor; nenhum rateio está autorizado por este desenho.
- Definir regras de carga e atualização, critérios de aceite e validações físicas em etapa posterior.

Esta entrega contém somente especificação lógica. A modelagem permanece sujeita a revisão, sem declaração de aprovação.
