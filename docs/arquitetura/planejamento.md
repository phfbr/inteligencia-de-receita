# Planejamento e arquitetura

## Contexto e objetivo

O projeto **Inteligência de Receita | Análise Comercial e Financeira** pretende organizar os dados públicos da Olist para apoiar análises comerciais e financeiras. A arquitetura proposta separa os arquivos de origem, os dados tratados, a camada dimensional e o consumo analítico, mantendo rastreabilidade entre as etapas.

O objetivo do planejamento é registrar uma direção de trabalho, não antecipar conclusões. A definição do modelo e das métricas dependerá do inventário, do profiling e da validação das regras de negócio com base nos dados disponíveis. As evidências da Etapa 2 estão registradas no [relatório de profiling](../qualidade/etapa2_profiling.md); este documento mantém as diretrizes e decisões ainda pendentes.

## Perguntas de negócio a investigar

As perguntas abaixo são hipóteses de investigação. A disponibilidade dos campos, a granularidade e as regras aplicáveis precisam ser confirmadas antes de responder:

- Como os pedidos e os valores associados se distribuem ao longo do tempo?
- Como a composição dos pedidos, os itens e o frete se relacionam com os valores pagos?
- Que diferenças existem entre os valores registrados em pedidos, itens e pagamentos?
- Como prazos e status do ciclo do pedido se relacionam com a experiência de entrega?
- Há diferenças relevantes entre categorias, vendedores, regiões ou outros recortes presentes nos dados?
- Como investigar recompra ao longo do período disponível, distinguindo `customer_id` de `customer_unique_id` e considerando os limites da janela de observação?
- Como os meios de pagamento e o parcelamento se distribuem entre pedidos, e como múltiplos registros de pagamento afetam essa leitura?
- Como produtos e vendedores contribuem para os valores comerciais observados, respeitando o grão dos itens e sem pressupor margem ou receita líquida?
- Quais aspectos dos dados limitam a interpretação financeira e comercial dos resultados?

Nenhuma dessas perguntas define, por si só, um indicador oficial ou uma regra de cálculo.

## Escopo da Etapa 1

Esta etapa contempla:

- criar a estrutura inicial de diretórios;
- documentar objetivos, perguntas, escopo, limitações e responsabilidades das camadas;
- registrar decisões e dependências que precisam ser resolvidas antes da implementação.

Não fazem parte desta etapa: obtenção ou carga de dados, profiling, instalação de dependências, pipelines, criação de tabelas, SQL analítico, definição final de fatos, dimensões ou indicadores, nem desenvolvimento de dashboards.

## Arquitetura proposta

O fluxo previsto é Bronze → Silver → Gold → Power BI. Bronze corresponde a arquivos locais; Silver e Gold correspondem a camadas no PostgreSQL. As pastas `sql/silver/` e `sql/gold/` guardarão futuramente o código dessas camadas, e não seus dados.

Python apoia o inventário e o profiling na Etapa 2, com a biblioteca padrão. Rotinas de carga permanecem para etapas futuras. SQL será usado para tratamentos, validações e construção do modelo no PostgreSQL. A divisão exata das transformações entre Python e SQL dependerá do profiling e deverá ser documentada.

### Bronze — arquivos de origem

`data/bronze/` será destinada aos CSVs originais da Olist, preservados sem alterações de conteúdo. A camada deverá manter os arquivos de origem identificáveis e evitar que transformações sobrescrevam os dados recebidos. Metadados de origem, versão, data de obtenção e checksums poderão ser registrados quando o processo de ingestão for planejado.

Na Etapa 2, os nove CSVs já disponíveis localmente foram inventariados, com nomes, tamanhos, registros, colunas e SHA-256 registrados em `docs/qualidade/profiling/`. A cobertura temporal observada está no relatório de qualidade. A origem externa e a versão publicada permanecem por confirmar; não houve download nesta execução.

### Silver — dados tratados no PostgreSQL

`sql/silver/` será destinada às definições SQL da camada tratada no PostgreSQL, depois que o perfil dos CSVs for conhecido. A Silver deverá documentar e aplicar tratamentos necessários, como padronização de tipos e campos, tratamento explícito de valores ausentes e validações de consistência, sem ocultar a origem das regras.

Os critérios específicos de limpeza e a estratégia de carga ainda não estão definidos. As transformações não devem descartar informação ou corrigir valores silenciosamente; cada regra deverá ter justificativa e validação.

### Gold — modelo dimensional no PostgreSQL

`sql/gold/` será destinada ao modelo dimensional para análise e consumo. A modelagem seguirá os princípios de Kimball: declarar a granularidade antes de modelar, manter fatos em grãos coerentes e usar dimensões conformadas quando apropriado.

A escolha de fatos, dimensões, chaves, histórico e métricas fica deliberadamente pendente até o profiling e a investigação das relações entre as fontes. Em especial, pedidos, itens e pagamentos podem representar grãos diferentes. Somar valores após relacionar essas estruturas sem controlar a granularidade pode duplicar valores de pedidos, itens ou pagamentos. Os relacionamentos e a regra de agregação devem ser avaliados antes de qualquer medida ser publicada.

### Power BI — consumo da Gold

`powerbi/` será destinada aos artefatos de consumo analítico. O Power BI deverá consumir a camada Gold no PostgreSQL, evitando reproduzir no relatório regras de transformação que deveriam estar documentadas e tratadas nas camadas anteriores.

Relatórios, medidas, filtros, controles de acesso, atualização e publicação serão planejados após a estabilização e validação do modelo Gold. Nenhum dashboard ou indicador está definido nesta etapa.

### Granularidade e prevenção de dupla contagem

Como exemplo exclusivamente hipotético, um pedido com três itens e dois registros de pagamento pode gerar seis linhas ao combinar itens e pagamentos apenas pela chave do pedido. Nesse resultado, valores de itens podem aparecer duas vezes e valores de pagamentos, três vezes. Esse exemplo ilustra um risco de relacionamento; não é uma constatação sobre os arquivos da Olist.

O profiling deverá verificar unicidade, cardinalidade, registros sem correspondência e totais antes e depois das combinações. A abordagem Kimball orientará a seleção do processo de negócio, a declaração do grão e, depois, a escolha de dimensões e fatos. Estruturas em grãos diferentes deverão ser avaliadas separadamente; eventual agregação prévia ou análise por dimensões conformadas será decidida com base nas evidências. Remover linhas repetidas ou aplicar uma soma distinta não será considerado solução automática para multiplicação de valores.

## Escopo funcional e limites de interpretação

O trabalho se restringe à análise possível com os dados públicos da Olist selecionados para o projeto. Não se presume acesso a sistemas internos, definições contábeis da empresa, custos, margens, impostos, reembolsos, cancelamentos financeiros ou contexto operacional que não esteja documentado nas fontes disponíveis.

Os dados públicos podem ser históricos, anonimizados ou limitados a campos e períodos específicos. Identificadores anonimizados não devem ser tratados como identidade real de pessoas ou empresas. A cobertura, a semântica de cada campo e a representatividade dos registros precisam ser verificadas no profiling; não se deve inferir comportamento atual da Olist ou causalidade apenas a partir de associações observadas.

Também será necessário confirmar como os arquivos representam status, datas, valores, frete, pagamentos e possíveis eventos posteriores ao pedido. A presença ou ausência desses conceitos não é presumida nesta documentação.

## Etapas previstas

1. **Planejamento e arquitetura** — definir a estrutura, registrar objetivos, perguntas, responsabilidades e decisões pendentes. Esta documentação corresponde a essa etapa e não a declara aprovada.
2. **Inventário e profiling** — obter e catalogar os arquivos autorizados; examinar esquema, granularidade, cobertura, qualidade, chaves e relações entre conjuntos de dados.
3. **Regras e desenho da Silver** — propor e validar critérios de padronização, tipos, tratamento de dados ausentes, consistência e rastreabilidade.
4. **Implementação e validação da Silver** — carregar e tratar os dados no PostgreSQL, com verificações documentadas e testes adequados.
5. **Desenho da Gold** — declarar o grão de cada estrutura dimensional, avaliar relações e duplicidades potenciais, e só então selecionar fatos, dimensões e métricas.
6. **Implementação e validação da Gold** — materializar o modelo dimensional no PostgreSQL e verificar totais e reconciliações conforme regras aprovadas.
7. **Consumo no Power BI** — construir relatórios sobre a Gold, validar filtros e medidas e documentar limitações de interpretação.
8. **Documentação e publicação** — consolidar arquitetura, dicionário, regras, evidências de qualidade, instruções de reprodução e limitações; preparar a publicação dos artefatos após revisão e autorização, sem expor credenciais ou dados indevidos.

As etapas são uma sequência de trabalho proposta, não um compromisso de que fontes, métricas ou resultados já foram confirmados.

## Decisões pendentes

- Quais arquivos e versão do conjunto público da Olist serão utilizados, e qual sua origem e licença aplicável?
- Qual será o método de obtenção, armazenamento, versionamento e registro dos arquivos originais?
- Qual versão do PostgreSQL, ambiente de execução, convenção de nomes e estratégia de carga serão adotados?
- Qual é a granularidade observada de cada arquivo e quais chaves permitem relacioná-los sem perda ou multiplicação indevida de linhas?
- Como serão interpretados estados do pedido, datas, valores, frete, pagamentos, parcelas, cancelamentos e demais eventos, se disponíveis?
- Quais critérios de qualidade e reconciliação serão exigidos em cada camada?
- Quais fatos, dimensões, chaves e regras de histórico são apropriados, após a análise dos dados?
- Quais métricas serão definidas, com quais denominadores, filtros e tratamento de duplicidades?
- Como serão configurados o acesso ao PostgreSQL, as credenciais fora do repositório, a atualização do Power BI e a publicação dos relatórios?

As decisões devem ser registradas junto com sua justificativa e evidências, sem transformar hipóteses em regras definitivas antes de serem verificadas.

## Evidências necessárias nas próximas etapas

O inventário deverá registrar origem, licença, versão e cobertura dos arquivos. O profiling deverá documentar tipos observados, valores ausentes, duplicidades, chaves candidatas, cardinalidades e consistência de datas e valores. Esses registros ficarão em `docs/qualidade/`, sem antecipar resultados ou limites de aceitação.

Antes da implementação da Silver, será necessário documentar regras de tratamento e critérios de qualidade. Antes do desenho definitivo da Gold, será necessário conhecer os grãos e relacionamentos e esclarecer a interpretação dos valores financeiros. Valor de itens, frete e pagamentos não devem ser chamados automaticamente de receita contábil, receita líquida ou lucro; essas interpretações exigem definições e informações compatíveis.

Antes do consumo no Power BI, deverão existir reconciliações entre as camadas, documentação das regras e verificação do comportamento das agregações e filtros. Tolerâncias, exclusões e critérios de aceite permanecem pendentes. Esses pontos orientam o trabalho futuro e não constituem aprovação desta etapa.

## Princípios de trabalho

- Preservar os arquivos de origem e manter rastreabilidade das transformações.
- Declarar e respeitar a granularidade antes de combinar ou agregar dados.
- Validar relações entre pedidos, itens e pagamentos para prevenir dupla contagem.
- Distinguir valores observados na fonte de conceitos financeiros que dependam de regras externas.
- Documentar incertezas, exclusões, tratamentos e limitações de cada resultado.
- Não apresentar análises como representativas ou causais sem evidência adequada.
