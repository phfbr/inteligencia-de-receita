# Etapa 6B — Implementação inicial do modelo semântico

## Situação da entrega

Este documento apresenta o procedimento para conectar o Power BI Desktop ao PostgreSQL e configurar o modelo inicial aprovado no [planejamento da Etapa 6A](planejamento_modelo_semantico.md). A execução no Desktop continua pendente. Não foram criados medidas DAX, tabelas adicionais, relatórios, visuais, arquivo Power BI ou relacionamentos nesta sessão.

Em 8 de novembro de 2026, foram efetivamente realizadas:

- leitura do planejamento aprovado, dos DDLs [das dimensões](../../sql/gold/001_dimensoes.sql) e [dos fatos](../../sql/gold/003_fatos.sql), dos catálogos registrados nas etapas 4B/4C e das referências da [Etapa 5](../qualidade/etapa5_validacao_analitica.md);
- busca no workspace por PBIP, PBIX, TMDL, BIM e PBIR: nenhum encontrado; `powerbi/` contém somente `.gitkeep`. Não foram encontradas ferramentas conectadas de edição Power BI, nem processos `PBIDesktop` ou `msmdsrv` em execução nesta sessão. Isso não demonstra que o aplicativo esteja desinstalado;
- conexão efetiva usando a configuração local protegida existente, sem registrar ou alterar credenciais. O banco retornou `inteligencia_receita_db`, PostgreSQL `18.6`, marcador `inteligencia_receita:exclusive:v1` e `transaction_read_only = on`;
- inspeção do catálogo atual e dos três campos monetários em uma transação `REPEATABLE READ READ ONLY`, encerrada com `ROLLBACK`. Foram confirmadas nove tabelas Gold, 78 colunas físicas, nove PKs e 17 FKs dimensionais validadas, coerentes com os DDLs. Não houve DDL, DML ou alteração de permissões.

O acesso protegido ao `psql` não constitui acesso ao motor Power BI e não transfere automaticamente a autenticação para o Desktop. **A precisão NUMERIC → Power Query → modelo importado não foi validada. Medidas monetárias permanecem bloqueadas até essa conferência.** As contagens de importação e referências analíticas abaixo são expectativas aprovadas; não representam uma carga Power BI executada.

## 1. Inventário a importar

Selecionar exclusivamente as nove tabelas do schema `gold`, mantendo os nomes. O inventário abaixo combina o catálogo físico conferido nesta sessão com a seleção de colunas aprovada. As sete colunas numéricas descritivas de produtos ficam fora do modelo inicial; nenhuma outra coluna será removida.

| Tabela Gold | Grão e chave | Colunas físicas / importar | Linhas esperadas no Power BI |
| --- | --- | ---: | ---: |
| `dim_clientes` | `cliente_sk`; membro regular por `customer_unique_id` | 3 / 3 | 96.098 |
| `dim_produtos` | `produto_sk`; membro regular por `product_id` | 12 / 5 | 32.953 |
| `dim_vendedores` | `vendedor_sk`; membro regular por `seller_id` | 6 / 6 | 3.097 |
| `dim_calendario` | `data_sk`; dia civil para membros regulares | 6 / 6 | 1.316 |
| `dim_localizacao` | `localizacao_sk`; tupla exata de CEP/cidade/UF | 5 / 5 | 15.036 |
| `dim_forma_pagamento` | `forma_pagamento_sk`; membro regular por `payment_type` | 3 / 3 | 7 |
| `fato_pedidos` | `order_id` | 15 / 15 | 99.441 |
| `fato_itens_pedido` | `order_id + order_item_id` | 16 / 16 | 112.650 |
| `fato_pagamentos` | `order_id + payment_sequential` | 12 / 12 | 103.886 |

São 71 colunas importadas, distribuídas nas mesmas nove tabelas, sem alterar sua granularidade. As contagens dimensionais incluem dois membros especiais em cada dimensão. Identidades naturais são únicas entre membros regulares; os identificadores naturais nulos dos técnicos não devem substituir a SK no lado 1.

### Colunas e tipos por tabela

Na tabela seguinte, **inteiro** significa número inteiro de 64 bits no Power Query (`Int64.Type`) e número inteiro no modelo; **texto**, `type text`; **data**, `type date`; **data/hora**, `type datetime`; **decimal fixo**, `Currency.Type` no Power Query e número decimal fixo no modelo, condicionado aos testes de precisão. O nome técnico Currency não confirma moeda nem exige formatação com símbolo.

| Tabela | Configuração das colunas importadas |
| --- | --- |
| `dim_clientes` | Inteiro: `cliente_sk`. Texto: `customer_unique_id`, `membro_tipo` |
| `dim_produtos` | Inteiro: `produto_sk`. Texto: `product_id`, `product_category_name`, `product_category_name_english`, `membro_tipo` |
| `dim_vendedores` | Inteiro: `vendedor_sk`. Texto: `seller_id`, `seller_zip_code_prefix`, `seller_city`, `seller_state`, `membro_tipo` |
| `dim_calendario` | Inteiro: `data_sk`, `ano`, `mes`, `dia_mes`. Data: `dia`. Texto: `membro_tipo` |
| `dim_localizacao` | Inteiro: `localizacao_sk`. Texto: `customer_zip_code_prefix`, `customer_city`, `customer_state`, `membro_tipo` |
| `dim_forma_pagamento` | Inteiro: `forma_pagamento_sk`. Texto: `payment_type`, `membro_tipo` |
| `fato_pedidos` | Texto: `order_id`, `customer_id`, `order_status`. Data/hora: `order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date`. Inteiro: `cliente_sk`, `localizacao_sk`, `data_compra_sk`, `data_aprovacao_sk`, `data_transportadora_sk`, `data_entrega_sk`, `data_previsao_entrega_sk` |
| `fato_itens_pedido` | Texto: `order_id`, `order_item_id`, `product_id`, `seller_id`, `customer_id`, `order_status`. Data/hora: `shipping_limit_date`, `order_purchase_timestamp`. Inteiro: `cliente_sk`, `localizacao_sk`, `produto_sk`, `vendedor_sk`, `data_compra_sk`, `data_limite_envio_sk`. Decimal fixo candidato: `price`, `freight_value` |
| `fato_pagamentos` | Texto: `order_id`, `payment_sequential`, `payment_type`, `customer_id`, `order_status`. Data/hora: `order_purchase_timestamp`. Inteiro: `cliente_sk`, `localizacao_sk`, `forma_pagamento_sk`, `data_compra_sk`. `payment_installments`: manter a representação numérica da origem, sem soma; converter para inteiro somente após comprovar domínio integral e faixa. Decimal fixo candidato: `payment_value` |

Em produtos, excluir somente `product_name_lenght`, `product_description_lenght`, `product_photos_qty`, `product_weight_g`, `product_length_cm`, `product_height_cm` e `product_width_cm`. **Divergência documental de contagem:** o planejamento menciona oito atributos numéricos descritivos, mas o DDL e o catálogo efetivo contêm sete. A seleção nominal aprovada de cinco colunas de produtos permanece a mesma. O total físico efetivo é **78 colunas**, sendo 35 dimensionais e 43 factuais; a seleção resulta em **71 colunas importadas**. Registrar essa constatação sem reescrever o planejamento aprovado ou acrescentar campo inexistente.

## 2. Preparação do Desktop e credenciais

1. Abrir o Power BI Desktop e anotar sua versão em **Ajuda → Sobre**. Este guia usa os nomes usuais dos menus, com equivalentes em inglês para opções que variam conforme a versão. Se aparecer uma tela diferente, conferir a opção correspondente; não habilitar recursos de prévia para reproduzir o procedimento.
2. Antes de obter dados, acessar **Arquivo → Opções e configurações → Opções → Arquivo atual → Carregamento de dados**. Na seção de inteligência temporal, desmarcar **Data/hora automática (Auto date/time)**. Na seção de relacionamentos, desmarcar **Importar relacionamentos de fontes de dados no primeiro carregamento**, **Atualizar ou excluir relacionamentos ao atualizar dados**, se disponível, e **Detectar automaticamente novos relacionamentos após carregar os dados**. Não usar o botão de detecção automática posteriormente. As opções globais de data/hora afetam novos arquivos; conferir principalmente o arquivo atual. Referências: [data/hora automática](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-auto-date-time) e [opções de relacionamentos](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-create-and-manage-relationships).
3. Confirmar localmente o host e a porta do PostgreSQL já configurado. No conector, o servidor será `HOST_CONFIRMADO:PORTA_CONFIRMADA` e o banco, **`inteligencia_receita_db`**. O texto em maiúsculas é um marcador de preenchimento, não um endereço real; não presumir porta padrão ou servidor remoto.
4. Para consumo, usar uma identidade dedicada de leitura, com conexão ao banco, acesso ao schema Gold e leitura das nove tabelas, sem privilégios administrativos ou de escrita. **Não recomendar `postgres` como credencial de produção.** Se esse usuário ainda não existir ou não tiver acesso, registrar a pendência para o responsável pelo banco. Este guia não cria usuário, concede privilégios, modifica autenticação ou pede exposição da senha.
5. A credencial existente dos executores locais fica protegida fora do repositório; ela não deve ser exportada para M, parâmetros, URLs, capturas de tela ou scripts do Power BI. A autenticação do Desktop deve ser informada exclusivamente no diálogo local do conector e gerida por **Configurações da fonte de dados → Editar permissões**. Não enviar senha ao chat. Não criar `.env` ou arquivo auxiliar com segredo.

## 3. Conexão PostgreSQL → Import

1. Selecionar **Página Inicial → Obter dados → Mais → Banco de dados → Banco de dados PostgreSQL**.
2. Informar servidor e banco confirmados acima e selecionar **Importar (Import)**, nunca DirectQuery. Em **Opções avançadas**, deixar a instrução SQL vazia. Desmarcar **Incluir colunas de relacionamento**, se a opção estiver presente: não serão expandidas tabelas relacionadas; as FKs escalares necessárias devem permanecer. Conferir as colunas efetivamente retornadas pelo conector.
3. Em autenticação, selecionar **Banco de dados**, preencher o usuário de leitura e a senha somente no diálogo local. Não reutilizar automaticamente uma credencial administrativa salva. Não ignorar falha de certificado ou reduzir a proteção da conexão como solução genérica; a configuração de transporte deve corresponder ao ambiente autorizado, sem alterações no servidor nesta etapa.
4. No Navegador, habilitar seleção múltipla e selecionar **apenas** as nove tabelas do inventário sob `gold`. Não selecionar o banco inteiro, `silver`, `public`, tabelas de sistema ou relacionamentos de navegação. Usar **Transformar dados**, em vez de carregar imediatamente.
5. No Editor do Power Query, confirmar que há nove consultas com carregamento habilitado e que cada etapa de navegação aponta a uma tabela `gold`. Não criar consultas de exemplo, parâmetros de senha, tabelas auxiliares ou mesclagens. Aplicar a seleção de colunas e os tipos da seção 1.
6. Conferir os testes preliminares da seção 5 antes de **Fechar e aplicar**. Depois da carga, confirmar o modo **Import** nas propriedades das nove tabelas e os tipos no modelo: o tipo exibido na prévia do Power Query, isoladamente, não prova o tipo armazenado no modelo.

O conector PostgreSQL suporta Import e autenticação por banco de dados. Versões recentes do Desktop incluem o provedor necessário; se houver erro de provedor, verificar a versão e a documentação antes de instalar qualquer componente. Nenhuma instalação foi realizada. Referência do procedimento: [conector PostgreSQL do Power Query](https://learn.microsoft.com/en-us/power-query/connectors/postgresql).

## 4. Transformações mínimas e preservação

Em cada consulta, manter somente origem, navegação, seleção de colunas quando necessária e tipagem explícita. Revisar etapas automáticas de “Tipo alterado” antes de mantê-las. Não executar remoção de duplicatas, limpeza de texto, substituição de valores, remoção de erros, substituição de nulos por zero, agrupamento, merge ou expansão de navegação. Não filtrar status, membros especiais ou pedidos sem filhos.

IDs e CEPs devem permanecer texto desde a navegação, sem passagem por inteiro ou decimal. Converter de volta para texto depois de perder zeros não recupera o original. Não transformar `order_item_id` e `payment_sequential` em contadores ou medidas. Não alterar grafias, caixa, espaços ou acentos.

Para timestamps PostgreSQL sem fuso, manter data/hora, sem `datetimezone`, conversão para UTC/local ou extração de dia em substituição ao original. A relação usa a SK já materializada na Gold; não recalcular a SK por interpretação do timestamp. O campo `dim_calendario.dia` permanece data. Conferir horas, segundos e eventual precisão fracionária em comparação com a origem; se houver perda no motor, registrar a limitação sem alterar a Gold.

`payment_installments` é atributo não aditivo. Sem confirmação de domínio integral, não impor inteiro. Preservar zeros e nulos; depois, definir **Não resumir** no modelo. Fazer o mesmo para identificadores, SKs, componentes civis e demais atributos. Os campos monetários também ficarão sem agregação implícita nesta etapa: não arrastar colunas para visuais nem criar medidas rápidas.

Após carregar, ocultar SKs/FKs e identificadores redundantes da navegação comum, sem excluir as colunas ou ocultá-las das verificações técnicas. Manter os nomes da origem para permitir conferir o inventário. Nenhuma formatação com símbolo de moeda deve ser aplicada.

## 5. Precisão monetária: evidência SQL e bloqueio no Power BI

### Verificações efetivamente executadas na origem

A inspeção de leitura desta etapa retornou:

| Campo | Linhas | Nulos | Mínimo | Máximo | Maior escala | Soma exata |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `price` | 112.650 | 0 | 0,85 | 6.735,00 | 2 | 13.591.643,70 |
| `freight_value` | 112.650 | 0 | 0,00 | 409,68 | 2 | 2.251.909,54 |
| `payment_value` | 103.886 | 0 | 0,00 | 13.664,08 | 2 | 16.008.872,12 |

Nos três campos houve **zero valores que perderiam casas ao limitar a quatro casas decimais** e **zero valores fora da faixa decimal fixa**. As somas dos valores absolutos coincidiram com as somas acima e ficaram dentro da faixa: nesta versão, os agregados por subconjunto desses valores não excedem esse limite. Esse teste comprova compatibilidade de domínio da origem com o candidato decimal fixo; não comprova o caminho do conector ou do motor Power BI.

O tipo decimal fixo tem quatro casas e faixa até 922.337.203.685.477,5807 em magnitude. O decimal comum usa ponto flutuante. Não escolher o segundo por conveniência nem usar formatação de duas casas como prova de precisão. Referência: [tipos numéricos do Power BI](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-data-types).

Consulta reproduzível utilizada para o domínio monetário, somente leitura:

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
WITH valores AS (
    SELECT 'price' AS campo, price AS valor FROM gold.fato_itens_pedido
    UNION ALL
    SELECT 'freight_value', freight_value FROM gold.fato_itens_pedido
    UNION ALL
    SELECT 'payment_value', payment_value FROM gold.fato_pagamentos
)
SELECT campo, count(*) AS linhas,
       count(*) FILTER (WHERE valor IS NULL) AS nulos,
       min(valor)::text AS minimo, max(valor)::text AS maximo,
       max(scale(valor)) AS escala_maxima,
       count(*) FILTER (WHERE valor <> trunc(valor, 4)) AS perda_em_4_casas,
       count(*) FILTER (WHERE abs(valor) > 922337203685477.5807) AS fora_da_faixa,
       sum(valor)::text AS soma, sum(abs(valor))::text AS soma_absoluta
FROM valores GROUP BY campo ORDER BY campo;
ROLLBACK;
```

A instrução acima é equivalente ao teste executado, apresentado de forma legível; não é instrução de importação e não cria tabela. A fonte foi mantida estática durante a inspeção. Não há evidência de atualização no Desktop nesta sessão.

### Testes obrigatórios no caminho de importação — todos pendentes

| Teste | Como verificar e critério de sucesso |
| --- | --- |
| P1 — tipo e conversão | Conferir cada coluna monetária no Power Query e no modelo como decimal fixo. Registrar os tipos retornados pelo conector antes e depois da conversão; não aceitar etapa intermediária que arredonde ou reduza a escala. Conversão sem erro não basta para comprovar exatidão |
| P2 — domínio integral | Na análise de qualidade do Power Query, selecionar **conjunto de dados inteiro**, não as primeiras mil linhas. Confirmar linhas, nulos, mínimos, máximos e ausência de erros. Prévia não equivale à tabela importada; verificar novamente depois de carregar |
| P3 — conteúdo por chave | Comparar os valores brutos de **todas** as linhas importadas com a origem, por `order_id + order_item_id` e `order_id + payment_sequential`. Exigir zero diferenças decimais, mesmas chaves, nulos e zeros. Exportação ou leitura do motor deverá preservar todos os registros e dígitos; copiar células formatadas ou uma amostra não satisfaz esse teste |
| P4 — agregados | Conferir somas gerais, delivered, por mês e por status e os grupos aplicáveis de produto/categoria/vendedor ou método, contra a Etapa 5. Exigir igualdade exata na escala da origem; não comparar apenas números exibidos com duas casas nem aceitar tolerância por ponto flutuante |
| P5 — soma no motor | Confirmar que os valores e a precisão permanecem corretos **no modelo carregado**, não apenas em cálculo dobrado para PostgreSQL ou na prévia do Power Query. Registrar tipo efetivo e mecanismo de leitura do resultado |
| P6 — persistência | Depois de atualização e reabertura do arquivo, repetir tipos, contagens e a comparação exata; nenhuma configuração automática pode voltar a converter os campos |

Esta etapa não dispõe de leitor/exportador do modelo nem cria DAX para executar P3–P5. O mecanismo de leitura integral do motor precisa ser definido e autorizado quando houver acesso efetivo ao Desktop ou ao projeto. Se a interface disponível só permitir amostragem, registrar a verificação integral como pendente. Não declarar precisão aprovada por inspeção visual ou porque as somas SQL fecharam. A criação de medidas monetárias só deve prosseguir após essas evidências; nenhuma foi autorizada por esta entrega.

## 6. Criar manualmente os 17 relacionamentos

Após a importação, abrir **Modelagem → Gerenciar relacionamentos → Novo** ou o comando equivalente na exibição de modelo. Para cada linha abaixo, selecionar exatamente as colunas indicadas. Definir cardinalidade **um para muitos (1:*)**, dimensão no lado 1, fato no lado muitos, e direção de filtro cruzado **Única (Single), dimensão → fato**. Se a caixa apresentar o fato primeiro, a cardinalidade pode aparecer como muitos para um (*:1); conferir os lados, não apenas a ordem dos nomes.

Definir explicitamente **Tornar este relacionamento ativo** conforme a matriz, sem aceitar o estado sugerido pelo Desktop. Relações inativas mantêm os mesmos lados e direção; aparecem tracejadas na exibição de modelo.

| Nº | Lado 1: dimensão.coluna | Lado N: fato.coluna | Estado | Papel |
| --- | --- | --- | --- | --- |
| 01 | `dim_clientes.cliente_sk` | `fato_pedidos.cliente_sk` | Ativo | Identidade |
| 02 | `dim_localizacao.localizacao_sk` | `fato_pedidos.localizacao_sk` | Ativo | Contexto do pedido |
| 03 | `dim_calendario.data_sk` | `fato_pedidos.data_compra_sk` | Ativo | Compra |
| 04 | `dim_calendario.data_sk` | `fato_pedidos.data_aprovacao_sk` | Inativo | Aprovação |
| 05 | `dim_calendario.data_sk` | `fato_pedidos.data_transportadora_sk` | Inativo | Entrega à transportadora |
| 06 | `dim_calendario.data_sk` | `fato_pedidos.data_entrega_sk` | Inativo | Entrega ao cliente |
| 07 | `dim_calendario.data_sk` | `fato_pedidos.data_previsao_entrega_sk` | Inativo | Previsão de entrega |
| 08 | `dim_clientes.cliente_sk` | `fato_itens_pedido.cliente_sk` | Ativo | Identidade contextual |
| 09 | `dim_localizacao.localizacao_sk` | `fato_itens_pedido.localizacao_sk` | Ativo | Contexto do pedido |
| 10 | `dim_produtos.produto_sk` | `fato_itens_pedido.produto_sk` | Ativo | Produto |
| 11 | `dim_vendedores.vendedor_sk` | `fato_itens_pedido.vendedor_sk` | Ativo | Vendedor |
| 12 | `dim_calendario.data_sk` | `fato_itens_pedido.data_compra_sk` | Ativo | Compra contextual |
| 13 | `dim_calendario.data_sk` | `fato_itens_pedido.data_limite_envio_sk` | Inativo | Limite de envio |
| 14 | `dim_clientes.cliente_sk` | `fato_pagamentos.cliente_sk` | Ativo | Identidade contextual |
| 15 | `dim_localizacao.localizacao_sk` | `fato_pagamentos.localizacao_sk` | Ativo | Contexto do pedido |
| 16 | `dim_forma_pagamento.forma_pagamento_sk` | `fato_pagamentos.forma_pagamento_sk` | Ativo | Método |
| 17 | `dim_calendario.data_sk` | `fato_pagamentos.data_compra_sk` | Ativo | Compra contextual |

O resultado esperado é **12 ativos e cinco inativos**, distribuídos em sete ligações para pedidos, seis para itens e quatro para pagamentos. As 17 FKs do PostgreSQL estão validadas, mas não configuram automaticamente o modelo Power BI.

Não relacionar os fatos por `order_id`, `customer_id` ou qualquer outra coluna. Não ligar cliente a localização, nem produto a pagamento, nem vendedor a pagamento. Não usar filtro Ambos/Both, relacionamento N:N, deduplicação ou ponte para contornar erro do lado 1. Se uma SK dimensional não for única na importação, interromper a configuração e investigar a divergência.

Datas de compra filtram os três processos em paralelo. Produto/vendedor filtram somente itens; método, somente pagamentos. Não habilitar propagação fato → dimensão para tentar tornar filtros comuns. Status de um fato continua local. Os cinco papéis temporais inativos ficam preparados para avaliação futura, mas não serão ativados por medidas nesta etapa.

## 7. Calendário e membros especiais

Importar as 1.316 linhas de calendário: 1.314 dias regulares contíguos, de 2016-09-04 a 2020-04-09, mais os membros `-1` e `-2`, com dia nulo. Usar a SK inteira, não `dia`, como chave de relacionamento. Não filtrar os especiais nem substituir seu dia por 1900, 1970 ou outra data.

**Não marcar a dimensão completa como tabela de datas.** A coluna de data tem nulos técnicos e não cumpre os requisitos de marcação clássica. Manter Data/hora automática desligada; não gerar calendário adicional. Os atributos civis existentes atendem à navegação inicial. Referência: [requisitos da tabela de datas](https://learn.microsoft.com/en-us/power-bi/transform-model/desktop-date-tables).

`-1` representa não informado; `-2`, referência não encontrada. Mostrar os motivos distintamente quando for necessária auditoria, usando `membro_tipo` e SK. Não usar somente o campo natural nulo como agrupamento dos técnicos. `not_defined` é um método real com SK regular positiva; não deve ser convertido em `-1`. Não há criação de “não aplicável”.

O limite de envio de um item chega a 2020-04-09; isso não estende a cobertura de compras a 2020. Compra permanece o papel ativo e não representa recebimento. Datas ausentes não removem pedidos do total sem filtro temporal; o recorte por dias conhecidos naturalmente exclui ausências daquele papel e exige tratamento explícito em etapa posterior.

## 8. Checklist de validação no Desktop

Todos os itens abaixo estão **pendentes de execução e confirmação manual**, salvo as verificações SQL descritas no início. A prévia padrão do Power Query não é evidência de todas as linhas. Registrar versão do Desktop, data de atualização, fonte, consulta/tabela, resultado esperado, observado, diferença e responsável, sem credenciais. Não criar visuais ou tabelas para preencher este checklist.

- [ ] Somente nove consultas carregadas, todas navegando em `gold`, modo Import e sem consultas auxiliares. Confirmar a seleção corrigida de **71 colunas**.
- [ ] Opções de data/hora e relações automáticas desligadas no arquivo atual; ausência de tabelas automáticas de datas.
- [ ] Contagens importadas iguais ao inventário; conferir o conjunto completo após atualização, não somente as mil linhas da prévia.
- [ ] SKs inteiras de 64 bits, sem nulos e únicas nas seis dimensões, incluindo `-1` e `-2`. No perfil de coluna, usar quantidade de valores **distintos**, não confundir com quantidade de valores que ocorrem uma única vez. Nenhuma deduplicação aplicada.
- [ ] Grãos únicos nos fatos: pedido; pedido-item; pedido-sequência. O teste composto deve avaliar a tupla, sem concatenação ambígua nem remoção de registros. Conferência integral ainda depende de acesso ao conteúdo carregado.
- [ ] As 17 FKs importadas resolvem SKs dimensionais existentes. Conferir a correspondência por chave, inclusive técnicos; criação da relação 1:N isoladamente não prova ausência de órfãos ou de membro em branco introduzido pelo motor.
- [ ] Gerenciar relacionamentos mostra exatamente a matriz: 12 ativos, cinco inativos, todos 1:N/Single; nenhuma relação fato–fato ou dimensão–dimensão. Capturar a lista e as propriedades, sem dados de autenticação.
- [ ] IDs e CEPs continuam texto, preservando valores originais e zeros; nenhum status ou método foi normalizado. Timestamps conservam dia e hora sem mudança de fuso.
- [ ] Comparação textual conferida em todos os grupos relevantes. O PostgreSQL usa `COLLATE "C"`; o motor Power BI pode reunir representações que diferem em caixa. Relações por SK não garantem que o agrupamento por texto ou sua exibição permaneça literal. Testar categorias, cidade/UF e IDs; se houver colisão, registrar e decidir apresentação sem normalizar a origem. Não considerar essa colisão observada sem evidência.
- [ ] Calendário completo, especiais nulos, sem marcação de tabela de datas e sem datas fictícias. Preservar 160 aprovações ausentes, 1.783 datas de transportadora ausentes e 2.965 entregas ao cliente ausentes da referência SQL.
- [ ] Executados P1–P6, com zero diferenças monetárias por chave e por agregação. Não criar medidas monetárias enquanto a precisão no motor permanecer pendente.
- [ ] Verificadas as referências gerais e delivered da tabela seguinte, sem excluir cancelados ou pedidos sem filhos. Na etapa atual, não escrever DAX para obtê-las: as comparações no motor que exigem mecanismo ainda indisponível permanecem pendentes.
- [ ] Verificado o isolamento dos filtros conforme a matriz, sem habilitar bidirecionalidade. O teste funcional de medidas/interações fica para a etapa autorizada correspondente, pois esta não cria DAX ou visuais.
- [ ] Nenhuma medida, coluna calculada DAX, medida rápida, relatório, visual, view ou objeto de banco criado por este procedimento.

### Referências aprovadas da Etapa 5

| Controle | Geral | Delivered |
| --- | ---: | ---: |
| Pedidos distintos | 99.441 | 96.478 |
| Linhas de itens | 112.650 | 110.197 |
| Pedidos com itens | 98.666 | 96.478 |
| Soma de price | 13.591.643,70 | 13.221.498,11 |
| Soma de frete | 2.251.909,54 | 2.198.275,64 |
| Registros de pagamento | 103.886 | 100.756 |
| Pedidos com pagamentos | 99.440 | 96.477 |
| Soma de payment_value | 16.008.872,12 | 15.422.461,77 |
| Pedidos sem itens | 775 | 0 |
| Pedidos sem pagamento | 1 | 1 |
| Pedidos comparáveis | 98.665 | 96.477 |
| Diferenças absolutas superiores a 0,01 | 303 | 299 |

Distribuição geral de pedidos por status: approved 2, canceled 625, created 5, delivered 96.478, invoiced 314, processing 301, shipped 1.107 e unavailable 609. A referência mensal é a data de compra civil; comparar todos os meses com as consultas 03, 07 e 14 da [validação analítica](../../sql/validacoes/analitica/), sem preencher meses vazios automaticamente. Os oito entregues sem data de entrega continuam elegíveis por status.

Clientes: 96.096 identidades observadas; 93.358 elegíveis para RN07; 2.015 com delivered em pelo menos dois dias civis de compra distintos; proporção descritiva de 2,1583581482036890%. Esta é referência do horizonte completo, não uma medida criada nem KPI de retenção. Dois pedidos no mesmo dia não bastam. Filtros de produto, vendedor e método não podem distorcer essa população.

O método `not_defined` mantém três registros reais de pedidos canceled, com soma 0,00. Preservar categorias nulas e sem tradução, bem como fretes e pagamentos zero. Para a reconciliação, agregar itens e pagamentos independentemente por pedido antes da comparação; nunca unir seus detalhes. As 303 diferenças continuam dados observados, sem ajuste ou interpretação como perda, taxa ou estorno.

## 9. Responsabilidades e pendências

| Atividade | Realizado pelo Codex nesta sessão | Depende do Desktop/intervenção local |
| --- | --- | --- |
| Ler plano, DDL e evidências aprovadas | Sim | Não |
| Confirmar catálogo atual, PKs/FKs e domínio monetário na origem | Sim, somente leitura | Não substitui a inspeção da importação |
| Localizar projeto/ferramentas de edição existentes | Sim; nenhum recurso disponível encontrado | Disponibilizar/abrir o Desktop quando for executar |
| Preparar roteiro, tipos, relações e checklist | Sim, neste único documento | Seguir e registrar os resultados |
| Autenticar no conector e importar as nove tabelas | Não | Sim, com credencial de leitura e parâmetros locais confirmados |
| Configurar tipos e 17 relações no modelo | Não | Sim |
| Conferir precisão no conector, Power Query e motor | Não; somente domínio SQL conferido | Sim; P1–P6 pendentes |
| Conferir contagens, conteúdo, texto e integridade importados | Não | Sim, com mecanismo de auditoria integral a definir |
| Criar medidas ou testar interação de visuais | Não; fora do escopo | Somente em etapa posterior autorizada |

Antes da execução manual, resolver a disponibilidade da conta de leitura sem alterar permissões por este guia. Na importação, confirmar a versão do conector, a representação de timestamps e decimais e o mecanismo de conferência do motor. Registrar resultados e erros reais; nenhuma caixa deste checklist deve ser marcada com base apenas nas evidências PostgreSQL.

Permanecem as limitações de moeda e semântica financeira, cobertura estática, status sem histórico, causas das divergências e decisões futuras de RN07 sob seleções temporais/geográficas. Não há rateio de pagamentos por produto/vendedor, localização permanente de cliente, custo, lucro ou recebimento inferido. Nenhum arquivo aprovado foi alterado e nenhum auxiliar foi necessário para este roteiro.

Na revisão local do documento, as 17 relações foram comparadas programaticamente às definições dos executores Gold e às colunas dos DDLs, com correspondência integral e contagem de 12 ativas e cinco inativas. Foram conferidas nove tabelas, 78 colunas físicas, 71 selecionadas e todos os links locais, sem inconsistências. A comparação SHA-256 dos 212 arquivos preexistentes não encontrou alterações; somente este documento foi criado. Essas verificações são documentais e não marcam como concluído nenhum item manual do Desktop.
