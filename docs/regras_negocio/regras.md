# Regras de negócio — documentação preliminar

## Referência e alcance

Este documento formaliza preliminarmente as decisões RN01–RN08 fornecidas para o projeto. Sua aplicação lógica é descrita no [modelo dimensional](../modelagem/modelo_dimensional.md). As evidências vêm do [profiling](../qualidade/profiling/resultados.json) e do [diagnóstico](diagnostico.md), sem novos resultados calculados nesta entrega.

Cada regra distingue a orientação recebida, a consequência proposta para o modelo e as decisões ainda abertas. O registro não significa aprovação do conjunto de regras, implementação ou validação contábil. Não define indicadores finais.

## Decisões da consolidação estática

As dimensões têm chaves substitutas e preservam suas identidades naturais; os fatos mantêm como chaves naturais `order_id`, `order_id + order_item_id` e `order_id + payment_sequential`, sem substitutas factuais. A versão estática não usa SCD2 nem inventa vigências. As relações dimensionais são 1:N por chave substituta, conforme a matriz e os papéis de calendário do modelo.

O calendário representa o dia civil da fonte, sem inferir ou converter fuso. Os timestamps originais permanecem completos e rastreáveis, sem substituição pela data diária, arredondamento ou preenchimento artificial. A representação física candidata é `TIMESTAMP WITHOUT TIME ZONE` com precisão suficiente e texto original preservado. O dia regular usa `DATE`, separado da chave substituta do calendário.

Valores monetários, agregados e diferenças usam `NUMERIC` exato, sem passagem por ponto flutuante e sem correções automáticas. Precisão/escala limitadas só poderão ser adotadas após validação de que não há perda, overflow ou arredondamento. As evidências atuais de divergências são preservadas como dados observados, não como defeitos a corrigir por conveniência.

Quando uma dimensão aplicável não puder ser resolvida, os membros especiais distinguem “não informado” de “referência não encontrada”; “não aplicável” só é usado quando a condição estiver justificada por regra e evidência. Componentes parciais, identificadores e motivos permanecem rastreáveis. Invalidade informada recebe sinal específico, sem ser escondida como vazio. Códigos físicos e resolução tardia continuam pendentes. Não há criação de fatos fictícios ou união de identidades desconhecidas para classificar recompra.

## RN01 — Preservar pedidos

**Orientação:** manter todos os pedidos da origem, independentemente de status, presença de itens ou pagamentos e qualidade das datas. Preservar significa conservar o universo e os valores originais, com rastreabilidade; não significa que todo pedido seja elegível como venda concluída.

**Evidência:** dos 99.441 pedidos, 775 não têm itens e um não tem pagamento. Os sem itens são 603 `unavailable`, 164 `canceled`, cinco `created`, dois `invoiced` e um `shipped`. O pedido sem pagamento está em `delivered` e tem três itens. Nenhum deles deve desaparecer por uma junção interna com filhos.

**Consequência lógica:** `fato_pedidos` tem uma linha por `order_id`; fatos filhos preservam apenas os registros efetivamente existentes. Ausências são sinalizadas, sem criar itens ou pagamentos de valor zero. Referência dimensional ausente não autoriza eliminar a linha; aplicam-se as estratégias de membros especiais do modelo.

**Verificação futura:** reconciliar quantidade e conjunto de `order_id` com a origem; confirmar que o filtro comercial não modifica o universo preservado. Duplicidades futuras de chave exigem investigação, sem deduplicação silenciosa.

**Pendente:** política de atualização em versões futuras, chegada tardia e tratamento técnico de referências não resolvidas. A versão estática não reconstrói histórico nem usa SCD2; os status atuais são fotografias da extração, não uma sequência de eventos comprovada.

## RN02 — Vendas concluídas por `delivered`

**Orientação:** o recorte de vendas concluídas usa exclusivamente o status observado `delivered`. Essa classificação não transforma valor de item ou pagamento em receita contábil ou caixa.

**Evidência:** há 96.478 pedidos nesse status; oito não têm data de entrega ao cliente e um não tem pagamento. Há também seis pedidos `canceled` com data de entrega ao cliente. Portanto, existência de data ou pagamento não substitui o critério de status.

**Consequência lógica:** a elegibilidade comercial deriva de `order_status = delivered`, mantendo o status original. Itens e pagamentos podem receber esse contexto a partir do pedido, sem excluir os demais registros dos fatos. Um entregue sem data continua elegível por RN02 e recebe sinal de qualidade separado. Um cancelado com data não se torna elegível.

**Verificação futura:** o recorte sobre a cópia atual deve reproduzir 96.478 pedidos; todas as classificações devem manter o vínculo unívoco ao pedido, sem contá-lo uma vez por item ou pagamento.

**Pendente:** significado contábil das medidas, reconhecimento temporal e efeito de alterações futuras de status. Não foi definida regra de estorno, receita líquida ou faturamento.

## RN03 — Separar `price` e `freight_value`

**Orientação:** manter o valor comercial do item e o frete em campos separados, no grão `order_id + order_item_id`.

**Evidência:** são 112.650 ocorrências de item com essa chave única e preenchida. Há 383 fretes zero. O diagnóstico comparou a soma de ambos aos pagamentos, mas essa comparação não comprova que tenham o mesmo significado financeiro.

**Consequência lógica:** os dois campos são medidas candidatas distintas de `fato_itens_pedido`, representadas em `NUMERIC` exato, sem correção automática. Uma soma conjunta pode apoiar reconciliação, sem substituir as parcelas originais. `order_item_id` não é quantidade e não deve multiplicar `price`. A contagem de linhas não será apresentada automaticamente como quantidade física vendida.

**Verificação futura:** reconciliar preço e frete separadamente antes e depois das transformações. Não repetir totais do pedido em cada item para depois somá-los. Zeros observados são preservados; ausência de item não comprova valor monetário zero.

**Pendente:** moeda, precisão física, significado de receita e eventual informação de quantidade ou custo. Nenhum custo logístico, margem ou tributo foi inferido.

## RN04 — Pagamentos não são recebimentos

**Orientação:** tratar `payment_value` como valor registrado na fonte de pagamentos, sem equipará-lo a recebimento, liquidação, fluxo de caixa ou receita reconhecida.

**Evidência:** há 103.886 registros, com chave única `order_id + payment_sequential`; 2.961 pedidos têm mais de um registro. Existem nove valores zero, dois registros com zero parcelas e três métodos `not_defined`. Não há data própria de pagamento ou recebimento comprovada entre os campos analisados.

**Consequência lógica:** `fato_pagamentos` mantém cada registro com método, valor em `NUMERIC` exato e parcelamento. `payment_installments` é atributo do registro; não multiplica `payment_value`, não gera parcelas artificiais e não determina datas de recebimento. `payment_sequential` identifica a ocorrência no pedido, sem afirmar sequência de liquidação. A data da compra pode ser contexto, mas não data de um evento financeiro.

**Verificação futura:** reconciliar chaves e valores por registro e por pedido, sem unir pagamentos às linhas de itens. Manter explícitos o pedido sem pagamento, os zeros e o método original `not_defined`.

**Pendente:** confirmação da semântica dos pagamentos e eventual fonte de liquidação, estornos ou recebimentos. Não existe regra de rateio para atribuir pagamento a produto ou vendedor.

## RN05 — Preservar divergências

**Orientação:** conservar valores divergentes e sua rastreabilidade, sem ajuste automático, compensação, arredondamento corretivo ou exclusão.

**Evidência:** entre 98.665 pedidos comparáveis, 98.089 têm igualdade exata, 273 têm diferença não nula de até 0,01 inclusive e 303 ultrapassam 0,01. Estes últimos são 299 `delivered`, dois `canceled` e dois `shipped`; há 264 diferenças positivas e 39 negativas, de -51,62 a 182,81.

**Consequência lógica:** agregar independentemente, com `NUMERIC` exato na futura implementação e `Decimal` nos diagnósticos existentes, preço e frete dos itens e valores de pagamentos, todos por pedido. A diferença assinada é `pagamentos − (preço + frete)`. Falta de uma fonte gera condição “não comparável”, não diferença zero. O recorte `abs(diferença) > 0.01` permanece diagnóstico; inclusive diferenças menores continuam preservadas. Não arredondar, compensar ou alterar valores para produzir igualdade.

**Verificação futura:** comparar conjuntos de pedidos e valores antes e depois, separando igualdade, pequena diferença, diferença acima do limiar exploratório e ausência de fonte. Uma junção de itens e pagamentos no grão original não é válida para essa conta.

**Pendente:** causa das divergências, eventual tolerância de negócio, classificação de exceções e política de acompanhamento. Não há comprovação de que diferenças representem descontos, taxas, estornos, perdas ou erros.

## RN06 — Identidade analítica via `customer_unique_id`

**Orientação:** usar `customer_unique_id` como identidade analítica do cliente e `customer_id` como identificador do registro de origem associado ao pedido.

**Evidência:** há 99.441 `customer_id` e 96.096 `customer_unique_id` distintos; 2.997 identificadores únicos se ligam a múltiplos pedidos. Cada `customer_id` aponta a uma única identidade na cópia analisada, sem órfãos no vínculo de pedidos com clientes.

**Consequência lógica:** a identidade natural de `dim_clientes` é `customer_unique_id`, com `cliente_sk` como chave substituta. O caminho de resolução é pedido → `customer_id` → `customer_unique_id`; preserva-se o identificador intermediário para auditoria. A localização é obtida do registro vinculado a cada pedido e resolvida separadamente em `dim_localizacao`, pela combinação exata dos componentes definida em RN08. Não se atribui endereço ou localidade permanente a `customer_unique_id`, nem se escolhe primeira/última localização para todos os pedidos.

**Verificação futura:** garantir resolução unívoca por registro e um membro regular por identidade natural na versão estática sem SCD2. Não confundir repetição legítima de identidade em clientes com duplicata de linha a eliminar. Referências não resolvidas devem preservar a chave original e a razão da ausência, distinguindo “não informado” e “referência não encontrada”.

**Pendente:** estabilidade do identificador na origem, política de futuras atualizações, códigos de membros especiais e eventual resolução tardia. O identificador anonimizado não comprova uma pessoa real nem permite unificação externa de identidades.

## RN07 — Recompra observada em dias de compra distintos

**Orientação:** recompra observada significa que um mesmo `customer_unique_id` tem pelo menos dois `order_id` distintos com status `delivered`, em pelo menos dois dias civis distintos de `order_purchase_timestamp`, conforme registrados na fonte. Dois pedidos no mesmo dia não bastam, mesmo que os horários sejam diferentes. Não se infere fuso ou independência das compras; o rótulo descreve somente o padrão observado na cobertura disponível.

**Evidência:** 2.997 clientes têm múltiplos pedidos de qualquer status, dos quais 2.801 têm pelo menos dois `delivered`. No conjunto com múltiplos pedidos de qualquer status, 290 clientes têm compras no mesmo segundo, 923 têm pedidos no mesmo dia e 2.149 têm pedidos em dias diferentes. Os dois últimos grupos podem se sobrepor. Não foi calculado neste documento o cruzamento final de elegibilidade com datas distintas; nenhuma dessas contagens é apresentada como recompra validada.

**Consequência lógica:** a classificação futura selecionará os pedidos `delivered`, resolverá a identidade e verificará ao menos dois dias de compra distintos por `customer_unique_id`. A referência é a compra, sem substituição por aprovação, entrega, previsão ou data de carga. Timestamps vazios ou inválidos são preservados e sinalizados, mas não fabricam um dia elegível; membros técnicos de calendário não contam como dias reais distintos. Não será criada uma ordem temporal real entre empates usando o desempate técnico por `order_id`. Identidades não resolvidas não serão agrupadas em um cliente fictício para satisfazer a regra.

**Verificação futura:** demonstrar que pedidos não elegíveis e múltiplos pedidos de um único dia não criam recompra; distinguir compra no mesmo segundo, mesmo dia e dias distintos da fonte. Validar o cruzamento conjunto de identidade, status e dia de compra, ainda não recalculado nesta entrega. A contagem de clientes precisa ser distinta, sem somar clientes repetidos entre períodos.

**Pendente:** execução da verificação sobre a cópia atual, atribuição de rótulos por pedido e representação dos pedidos posteriores no mesmo dia. A cobertura disponível é o universo desta definição; um horizonte adicional ou análise de coortes exigirá especificação própria. O tratamento de compras próximas ou potencialmente desdobradas ainda precisa de evidência; limites exploratórios de segundos ou horas não são regras de sessão e não comprovam compras independentes. Não há taxa ou indicador final definido.

## RN08 — Não usar geolocalização bruta em joins dimensionais

**Orientação:** não relacionar diretamente os fatos, ou o contexto de cliente, às linhas brutas de geolocalização para construir ou consumir dimensões.

**Evidência:** o arquivo tem 1.000.163 registros e 19.015 prefixos de CEP distintos; há 261.831 duplicatas exatas excedentes, e um prefixo aparece em até 1.146 registros. Logo, prefixo não é chave única do arquivo e uma junção pode multiplicar fatos. Não houve ainda validação geográfica externa ou decisão sobre coordenadas representativas.

**Consequência lógica:** `dim_localizacao` representa a tupla exata de `customer_zip_code_prefix`, `customer_city` e `customer_state` do registro de cliente associado ao pedido por `customer_id`, com chave substituta `localizacao_sk`. Os três componentes originais são preservados e comparados separadamente, sem remoção de espaços, mudança de caixa/acentos ou normalização. Tuplas idênticas compartilham membro regular; componentes distintos permanecem distintos, sem pressupor equivalência geográfica. Não haverá junção à geolocalização bruta. Nenhuma coordenada será escolhida por primeira linha, média ou outra regra improvisada. A Bronze permanece intacta.

**Verificação futura:** demonstrar um membro regular por combinação exata completa e que sua resolução não aumenta o número de linhas dos fatos. Verificar preservação de zeros à esquerda do prefixo de CEP e semântica de comparação textual no ambiente físico. Componentes obrigatórios ausentes resolvem “não informado”, preservando as partes disponíveis; uma combinação preenchida sem referência dimensional encontrada resolve “referência não encontrada”. Não descartar nem associar arbitrariamente. A localização de vendedor não substitui a do cliente no pedido.

**Pendente:** verificar quantidade de combinações exatas, componentes ausentes, grafias e domínio de comparação física. Padronização, equivalências geográficas ou enriquecimento só poderão ser propostas com evidência e decisão própria, sem alterar a identidade exata definida para esta versão. Qualquer futura derivação geográfica terá de especificar o próprio grão e sua regra antes de ser usada; esta regra não autoriza limpeza ou agregação da fonte bruta.

## Dependências comuns e estado do registro

Permanecem abertas a comprovação de origem, versão e licença; a unidade monetária; a validação de limites dos tipos físicos candidatos; as políticas de futuras atualizações; os códigos dos membros especiais e a resolução tardia; e os critérios de aceite para implementação. Chaves, ausência de SCD2 nesta versão, identidade exata de localização, dia civil da fonte e critério de recompra observada não permanecem como alternativas abertas. As distinções entre não informado, referência não encontrada e não aplicável, assim como a preservação de originais e inválidos, estão descritas no modelo lógico.

As oito regras foram documentadas como orientação preliminar, com suas evidências e limites. Nenhuma regra ou modelagem foi declarada aprovada. Não foram implementados SQL, PostgreSQL, Silver, Gold, DAX ou dashboards, e os arquivos de evidência anteriores permanecem preservados.
