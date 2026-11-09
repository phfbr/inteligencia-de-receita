# Etapa 4A — Implementação e execução da Silver PostgreSQL

## Reexecução mais recente com configuração protegida

A conexão e o isolamento de `inteligencia_receita_db` foram novamente confirmados em PostgreSQL 18.6. O marcador existente foi preservado, sem adoção ou alteração de objetos externos. A execução reutilizou os scripts e testes existentes, sem mudanças no código, nas regras de negócio ou na modelagem.

As duas cargas receberam `COMMIT` e produziram resultados idênticos. A falha deliberada antes do terceiro commit retornou SQLSTATE `22012`; a verificação somente leitura posterior confirmou integralmente a versão válida anterior. Foram executados **25 testes, todos com sucesso, sem casos ignorados**.

As nove tabelas mantiveram **1.550.922 registros**, com as contagens discriminadas abaixo. Tipos, nulos, chaves, valores originais, fingerprints e totalizações exatas coincidiram com a Bronze. Os nove SHA-256 das fontes permanecem iguais aos do profiling. Não houve erros de conversão. As 303 divergências monetárias conhecidas e os 13 produtos com categoria sem tradução foram preservados; não são divergências introduzidas pela carga.

Evidências desta reexecução: [resumo](etapa4_silver/conclusao_20261108T024814481530Z/conclusao.json), [25 testes](etapa4_silver/conclusao_20261108T024814481530Z/testes.log), [conferência final](etapa4_silver/conclusao_20261108T024814481530Z/verificacoes_finais.json), [primeira carga](etapa4_silver/conclusao_20261108T024814481530Z/integracao/first/resultado.json), [reexecução idempotente](etapa4_silver/conclusao_20261108T024814481530Z/integracao/second/resultado.json), [falha deliberada](etapa4_silver/conclusao_20261108T024814481530Z/integracao/rollback/resultado.json) e [conferência pós-rollback](etapa4_silver/conclusao_20261108T024814481530Z/integracao/verify/resultado.json).

Não houve bloqueio técnico nesta execução. Permanecem as pendências de procedência/licença, moeda e investigação das exceções da origem. Nenhuma aprovação de etapa foi declarada. As evidências das execuções anteriores foram preservadas.

## Execução anterior de referência

A Silver foi carregada e comparada integralmente à Bronze no banco exclusivo `inteligencia_receita_db`, em PostgreSQL **18.6**, com encoding `UTF8`. Foram concluídas duas cargas transacionais, uma falha deliberada antes do commit e uma verificação somente leitura após o rollback. As nove tabelas contêm **1.550.922 registros**, sem diferenças de contagem, valores tipados, textos originais, nulos ou fingerprints em relação às fontes. Nenhuma regra de negócio foi alterada e nenhum objeto Gold foi criado.

A execução final ocorreu em 7 de novembro de 2026, das 23:37 às 23:44 no horário de São Paulo; os arquivos registram os horários UTC equivalentes em 8 de novembro. O [resumo da conclusão](etapa4_silver/conclusao_20261108T023727669737Z/conclusao.json) tem estado `completed_verified`, lista de erros vazia e confirmação de idempotência e rollback. Os [25 testes passaram](etapa4_silver/conclusao_20261108T023727669737Z/testes.log), sem falhas ou casos ignorados.

A [conferência final independente](etapa4_silver/conclusao_20261108T023727669737Z/verificacoes_finais.json) reconcilia contagens, nulos, tipos, somas, hashes dos nove CSVs e artefatos usados. As regras de negócio, a modelagem, `requirements.txt` e o SQL de consultas de validação foram preservados.

| Execução real | Resultado | Evidência |
| --- | --- | --- |
| Primeira carga corrigida | `committed` | [Resultado](etapa4_silver/conclusao_20261108T023727669737Z/integracao/first/resultado.json) |
| Reexecução da mesma versão estática | `committed`; mesmos resultados | [Resultado](etapa4_silver/conclusao_20261108T023727669737Z/integracao/second/resultado.json) |
| Falha deliberada após carga e validações, antes do commit | `failed`, SQLSTATE `22012`, divisão por zero esperada | [Resultado](etapa4_silver/conclusao_20261108T023727669737Z/integracao/rollback/resultado.json) |
| Conferência após a falha | `verified_readonly`; versão válida anterior integralmente preservada | [Resultado](etapa4_silver/conclusao_20261108T023727669737Z/integracao/verify/resultado.json) |

O estado `failed` da terceira execução é parte do teste e não uma pendência de carga: o teste exige o SQLSTATE específico e a igualdade Bronze–Silver após a reversão. Não houve commit parcial nem criação de registros para compensar exceções.

## Histórico da preparação inicial

A execução inicial de `scripts/silver.py --mode prepare` havia terminado com estado `blocked` e `database_load_completed: false`, antes de qualquer carga no banco. Suas contagens e totais eram apenas observações dos CSVs. As evidências iniciais abaixo foram preservadas como histórico; não representam o estado final da Silver.

Foram encontrados os serviços `postgresql-x64-16` e `postgresql-x64-18` em execução e clientes instalados em `C:\Program Files\PostgreSQL`. O cliente consultado explicitamente informou `psql 16.15`. As sondagens `pg_isready` em `127.0.0.1:5432` e `127.0.0.1:5433` indicaram aceitação de conexões. Essas sondagens não comprovam autenticação, banco correto ou exclusividade.

Naquela preparação, não estavam configuradas `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `OLIST_PROJECT_DATABASE` nem credencial explícita por `PGPASSWORD` ou `PGPASSFILE`. Nenhuma senha foi presumida, impressa ou registrada; nenhum arquivo de credenciais foi procurado fora de uma configuração explícita. Não houve então tentativa de autenticação, instalação, inicialização ou alteração de serviços. O bloqueio foi posteriormente resolvido pela configuração local protegida descrita adiante.

Evidências desta entrega: [resultado.json](etapa4_silver/resultado.json), [execucao.log](etapa4_silver/execucao.log), [ambiente.log](etapa4_silver/ambiente.log), [manifesto.csv](etapa4_silver/manifesto.csv), [testes.log](etapa4_silver/testes.log) e [verificacoes.json](etapa4_silver/verificacoes.json).

## Arquivos e objetos implementados

- [scripts/silver.py](../../scripts/silver.py): preparação, verificação de conexão e destino, carga transacional e validação somente leitura. Reutiliza constantes, chaves candidatas e SHA-256 de `profiling.py` sem modificá-lo.
- [sql/silver/001_estrutura.sql](../../sql/silver/001_estrutura.sql): schema `silver`, nove tabelas, comentários de identificação e verificações de proteção. Deve ser usado pelo orquestrador, que configura o destino esperado e a transação; não é instrução para execução isolada.
- [sql/validacoes/silver.sql](../../sql/validacoes/silver.sql): consultas de contagem, integridade e reconciliação monetária, sem alteração de dados. O orquestrador também gera verificações obrigatórias específicas para os hashes e contagens da execução.
- [tests/test_silver.py](../../tests/test_silver.py): testes locais e teste de integração condicionado a conexão exclusiva configurada.
- [scripts/concluir_silver.ps1](../../scripts/concluir_silver.ps1): configuração local protegida e passagem temporária de parâmetros ao processo de execução, sem senha nos argumentos ou resultados.
- [scripts/concluir_silver.py](../../scripts/concluir_silver.py): inspeção do banco nominal, identificação de banco novo vazio e execução dos testes existentes, preservando os resultados de cada carga e da reversão.

O banco recebeu somente o schema `silver` e uma tabela por CSV, além dos índices das chaves técnicas e comentários de identificação. Não há tabela extra de auditoria, extensão, dimensão, fato dimensional, view, função persistente ou schema Gold. A auditoria usa colunas nas nove tabelas e arquivos locais de evidência. A inspeção inicial encontrou zero relações de usuário; o schema `public` foi preservado. Nenhum objeto preexistente foi removido.

| Tabela no schema `silver` | Registros Bronze observados | Registros Silver verificados |
| --- | ---: | --- |
| `olist_customers_dataset` | 99.441 | 99.441 |
| `olist_geolocation_dataset` | 1.000.163 | 1.000.163 |
| `olist_orders_dataset` | 99.441 | 99.441 |
| `olist_order_items_dataset` | 112.650 | 112.650 |
| `olist_order_payments_dataset` | 103.886 | 103.886 |
| `olist_order_reviews_dataset` | 99.224 | 99.224 |
| `olist_products_dataset` | 32.951 | 32.951 |
| `olist_sellers_dataset` | 3.095 | 3.095 |
| `product_category_name_translation` | 71 | 71 |
| **Total de registros de grãos diferentes** | **1.550.922** | **1.550.922** |

As linhas são registros CSV sem cabeçalho, respeitando campos com quebras de linha internas. O total é controle de inventário, sem interpretação comercial.

## Preservação, tipos e auditoria

Cada registro CSV gera uma linha, na mesma posição de origem, sem agrupamento, filtros de status, limpeza, deduplicação ou junção de enriquecimento. Os nomes e a ordem dos campos de negócio correspondem ao cabeçalho original, inclusive grafias como `product_name_lenght`.

| Domínio | Representação Silver | Regra |
| --- | --- | --- |
| Identificadores, prefixos de CEP, categorias, cidades, UF, métodos e status | `TEXT`; campos de negócio com comparação `COLLATE "C"` | Preservar zeros à esquerda, caixa, acentos e espaços. `order_item_id` e `payment_sequential` também são texto |
| Preço, frete, pagamentos e demais campos quantitativos reconhecidos | `NUMERIC` sem precisão/escala restritas | Conversão por `Decimal`, sem `float`, arredondamento, compensação ou multiplicação por parcelas |
| Datas e horas | `TIMESTAMP WITHOUT TIME ZONE` | Preservar horário da fonte, sem atribuir ou converter fuso. Timestamps com offset ou precisão superior a microssegundos não são truncados para caber |
| Campo CSV vazio após decodificação | `NULL` no campo de negócio e string vazia em `_raw_record` | Mapeamento explícito de ausência, coerente com o profiling. Não converter espaços, `NULL` textual ou `not_defined` automaticamente em ausência |
| Valor numérico ou timestamp não interpretável sem perda | `NULL` tipado, original integral em `_raw_record` e razão em `_conversion_errors` | Preservar a linha; distinguir falha de conversão de ausência original. Não houve ocorrência na cópia examinada |

Não se atribui ao CSV uma semântica de nulo que ele não declara: campos vazios entre aspas ou não são ambos strings vazias após o parser; aspas, separadores, BOM e bytes físicos continuam recuperáveis no CSV original identificado por SHA-256. `JSONB` preserva os valores textuais decodificados, não a serialização física do arquivo nem a ordem de suas chaves. Nenhum arquivo Bronze é regravado.

Cada tabela contém ainda:

| Coluna técnica | Tipo | Finalidade |
| --- | --- | --- |
| `_source_file` | `TEXT NOT NULL` | Nome do CSV de origem |
| `_source_sha256` | `TEXT NOT NULL` | SHA-256 completo do arquivo analisado |
| `_source_row` | `BIGINT PRIMARY KEY` | Posição do registro CSV, começando em 1 sem contar o cabeçalho; não é linha física |
| `_raw_record` | `JSONB NOT NULL` | Todos os campos originais como strings, inclusive textos de números, timestamps e vazios |
| `_conversion_errors` | `JSONB NOT NULL` | Campo e razão controlada da falha de conversão; objeto vazio quando não há falha |

A chave técnica por posição não deduplica chaves de negócio e não altera o grão de uma ocorrência por registro. Não foram impostas unicidades ou FKs de negócio que rejeitem exceções conhecidas. Sua verificação ocorre por consultas e comparação com a Bronze, preservando todas as ocorrências. Tabelas Silver não são os fatos ou dimensões do modelo Gold.

Cabeçalho inesperado, largura incorreta, mudança de hash, CSV não interpretável ou caractere NUL incompatível com a preservação em PostgreSQL interrompem a preparação/carga, sem descarte seletivo. Nesses casos não se declara carga concluída. A política para fontes de outra versão depende de investigação própria: esta implementação exige os hashes da versão estática do profiling existente.

## Confirmação de destino exclusivo

O orquestrador exige que `PGDATABASE` e `OLIST_PROJECT_DATABASE` coincidam. Depois, abre uma transação **somente leitura** para verificar o banco real e seus catálogos antes de enviar DDL ou alterações de dados. O destino precisa estar previamente provisionado e identificado pelo responsável como exclusivo deste projeto:

- comentário do banco exatamente `inteligencia_receita:exclusive:v1`;
- proprietário do banco igual ao usuário conectado;
- servidor PostgreSQL 14 ou superior e encoding `UTF8`;
- ausência de outros schemas de usuário além de `public` vazio e `silver` do projeto, sem tabelas, funções, tipos ou extensões de terceiros;
- se `silver` já existir, comentário `inteligencia_receita:silver:v1`, proprietário compatível e apenas os objetos reconhecidos pela especificação;
- tabelas existentes com comentários de identidade, estrutura, tipos e chave técnica compatíveis, sem defaults, triggers de usuário, regras, herança, RLS ou restrições extras não previstas.

O carregador `silver.py` não cria banco, não atribui ownership e não remove objetos externos para atender às verificações. A rotina de conclusão admite identificar somente o banco nominal `inteligencia_receita_db`, declarado exclusivo para este projeto, após inspeção somente leitura que confirme proprietário, estrutura permitida e ausência de relações de usuário. Se o comentário estiver vazio, essa rotina aplica o marcador em transação própria e repete a proteção; não sobrescreve comentário divergente nem adota objetos sem identificação. Foi esse o caso na primeira inspeção real, registrado na [tentativa inicial](etapa4_silver/conclusao_20261108T023319084089Z/conclusao.json). Nas execuções seguintes o marcador já existia e foi preservado. Não se deve marcar um banco compartilhado como exclusivo apenas para ultrapassar a proteção.

A conferência é repetida dentro da transação de escrita, após um lock consultivo comum às execuções deste carregador. O SQL em disco precisa corresponder ao gerador revisado; divergência de código interrompe a execução. Isso não substitui controle de acesso: o papel usado deve ser exclusivo do projeto, e outros processos não devem editar esses objetos durante a carga.

## Transação e idempotência estática

O modo `load` prepara arquivos temporários no cliente, valida cabeçalhos, conversões e hashes e confere a exclusividade. Só então envia uma única transação com criação dos objetos reconhecidos, substituição integral do conteúdo das nove tabelas e testes antes do `COMMIT`.

A reexecução usa `DELETE` apenas nas nove tabelas marcadas do projeto, seguido de `COPY FROM STDIN` com todas as ocorrências da mesma versão. Não usa `DROP`, `CASCADE`, `TRUNCATE`, deduplicação ou `ON CONFLICT` para ignorar registros. A substituição não fica visível parcialmente a outras transações; erro antes do commit impede a conclusão da carga. O comportamento do cliente com `ON_ERROR_STOP` e a leitura via `COPY FROM STDIN` são descritos na documentação oficial de [psql](https://www.postgresql.org/docs/16/app-psql.html) e [COPY](https://www.postgresql.org/docs/16/sql-copy.html).

Essa idempotência foi verificada com duas cargas reais da mesma versão estática e comparação dos resultados. Após uma terceira carga com falha deliberada antes do commit, a conferência integral também passou. As tabelas e suas estruturas foram reutilizadas, sem remoção de objetos. Não é carga incremental nem mecanismo de histórico. Em timeout, queda de conexão ou falha após envio de commit, o estado deve ser confirmado no banco antes de concluir se houve rollback ou repetir; não se presume um resultado que o cliente não confirmou.

Os arquivos temporários de COPY e SQL são removidos ao terminar o contexto de execução. Não contêm senhas; os dados são enviados pelo cliente, sem exigir acesso do serviço PostgreSQL à pasta Bronze. `psql` é chamado sem leitura de configuração de usuário (`-X`) e sem prompt de senha (`-w`). Detalhes privados de erros de conexão não são persistidos: registram-se código de saída e SQLSTATE, quando disponível, sem stderr bruto ou conteúdo das linhas.

## Execução reproduzível

Não foi necessário alterar `requirements.txt`: Python usa somente a biblioteca padrão e o cliente `psql` já instalado. No ambiente examinado, o Python funcional está em `<diretório local do Python>\python.exe`; o alias `python` do PATH já havia falhado nas etapas anteriores. Os comandos abaixo pressupõem um Python funcional e devem ser executados na raiz do projeto.

### Configuração local usada na conclusão

A senha é digitada apenas no prompt protegido do terminal local. O wrapper armazena uma credencial criptografada por DPAPI em `%TEMP%\inteligencia_receita_local\conexao.clixml`, fora do repositório e com acesso restrito ao usuário. No Windows, essa credencial só pode ser descriptografada pela mesma conta na mesma máquina, conforme a documentação de [Export-Clixml](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/export-clixml?view=powershell-5.1). Não é arquivo de senha em texto aberto.

```text
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\concluir_silver.ps1 -Configurar
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\concluir_silver.ps1 -Executar
```

`-Configurar` coleta host, porta, usuário e senha no terminal e fixa o banco nominal; não acessa o banco nem inicia carga. Uma configuração existente não é sobrescrita automaticamente. `-Executar` importa a configuração, disponibiliza as variáveis apenas ao processo corrente e filhos, e restaura o ambiente ao sair. Senhas não aparecem nos argumentos, SQL, logs ou arquivos versionados. A política de execução indicada vale somente para esse processo PowerShell, sem mudança persistente de política.

A conclusão reutiliza o teste de integração existente. A variável opcional `OLIST_DB_EVIDENCE_DIR` permite conservar seus quatro diretórios de resultado, em vez de apagá-los com o diretório temporário de testes. O resumo agrega a inspeção de isolamento, resultados dos testes, dados do catálogo e verificações numéricas reais. Não é necessário enviar credenciais ao chat.

### Alternativa por ambiente explícito

1. Configurar `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` e `OLIST_PROJECT_DATABASE` no ambiente do processo, com credencial por `PGPASSWORD` ou caminho explícito em `PGPASSFILE`. Não colocar senhas nos comandos, relatórios ou repositório. `OLIST_PSQL` é opcional para indicar o executável; sem ele, procura-se no PATH e nas instalações locais usuais. O carregador não lê `.env`, URIs ou serviços de conexão implicitamente.
2. Provisionar e comprovar o destino exclusivo conforme a seção anterior, sem usar banco compartilhado.
3. Executar preparação e inspeção somente leitura, em diretório novo:

```text
python scripts/silver.py --mode prepare --output docs/qualidade/etapa4_silver/preparacao_02
```

4. Após resolver os bloqueios, executar a carga transacional:

```text
python scripts/silver.py --mode load --output docs/qualidade/etapa4_silver/carga_01
```

5. Executar a comparação Bronze–Silver somente leitura:

```text
python scripts/silver.py --mode verify --output docs/qualidade/etapa4_silver/conferencia_01
python -m unittest discover -s tests -v
```

Cada diretório de evidência deve ser novo; resultados anteriores não são sobrescritos. `prepare` não escreve no banco. `verify` usa transação somente leitura. `load` só registra `database_load_completed: true` após retorno bem-sucedido do processo com commit. Um estado `blocked` não é carga concluída.

O teste de integração exige também `OLIST_RUN_DB_TESTS=1` no ambiente. Ele realiza duas cargas reais, compara os resultados, força divisão por zero antes de um terceiro commit e valida a versão anterior após o rollback. Portanto, só deve ser habilitado no banco dedicado ao projeto. Sem a variável, fica explicitamente marcado como não executado.

## Verificações Bronze–Silver

Antes do commit e no modo `verify`, o plano verifica:

- quantidade de registros, posição inicial/final e metadados de arquivo/hash de cada tabela;
- fingerprint SHA-256 ordenado de todos os valores textuais originais e razões de conversão, independente do hash dos bytes do CSV;
- tipos e estrutura física em catálogo, incluindo timestamps sem fuso, identificadores textuais e `NUMERIC` sem escala restritiva;
- igualdade campo a campo do valor tipado com sua representação original convertível, sem usar ponto flutuante;
- contagem de nulos e erros por coluna e somas exatas de todos os campos numéricos preparados;
- cardinalidade das chaves candidatas, incluindo as repetições esperadas de identidade de cliente, prefixo geográfico e avaliações;
- integridade referencial pedidos–clientes, itens–pedidos/produtos/vendedores, pagamentos–pedidos, avaliações–pedidos e produtos–tradução;
- consultas de observação da diferença entre pagamentos e itens mais frete, agregados separadamente por pedido.

O fingerprint transforma cada valor original em hexadecimal UTF-8, separa os campos de forma não ambígua, calcula um SHA-256 por registro e outro sobre a sequência desses hashes. Permite comparar multiplicidade e posição, inclusive registros idênticos. Na verificação SQL usa a função binária nativa [sha256](https://www.postgresql.org/docs/16/functions-binarystring.html), sem instalar extensão. Não substitui a preservação dos CSVs.

As referências são comparadas com a contagem observada na Bronze, não com a hipótese de que todas sejam perfeitas. Uma mudança em relação ao manifesto impede o commit; uma exceção já presente e documentada não é escondida nem “resolvida” por exclusão.

## Resultados locais da preparação inicial

A preparação examinou os nove CSVs e confirmou os hashes do profiling antes/depois, com 1.550.922 registros e **zero erros de conversão**. Identificadores e prefixos de CEP permanecem textos. Os detalhes por coluna, incluindo nulos e cardinalidades, estão em `resultado.json`.

Totalizações exatas da Bronze nesta execução:

| Campo | Total observado nos registros de sua fonte |
| --- | ---: |
| `price` | 13.591.643,70 |
| `freight_value` | 2.251.909,54 |
| `payment_value` | 16.008.872,12 |

Esses totais têm universos diferentes: incluem todos os itens ou todos os registros de pagamento, inclusive pedidos sem correspondência na outra fonte. Não constituem reconciliação global aprovada, recebimentos ou receita. Na futura comparação Silver, cada soma deve reproduzir exatamente sua própria fonte.

Na preparação inicial, os testes somaram 20 casos: **19 passaram e um teste de integração foi explicitamente não executado**. Foram cobertos os dez testes anteriores e nove novos testes locais, incluindo zeros à esquerda, decimal exato, timestamps sem deslocamento/truncamento, distinção de nulo e texto `\\N`, duplicatas, originais de valores inválidos, mudança de fonte, ausência de ambiente sem invocar `psql`, geração transacional do plano e supressão de senha fictícia nos erros. A execução final ampliou a cobertura para 25 casos e executou a integração real, sem casos ignorados.

Naquela preparação ainda não tinham sido executados DDL, COPY ou testes de catálogo, igualdade Bronze–Silver, reexecução e rollback no servidor. Essas verificações foram posteriormente concluídas na execução final documentada acima.

Durante a coleta do log de testes, a primeira leitura como UTF-8 encontrou saída do subprocesso em codificação Windows. A captura foi refeita com `PYTHONIOENCODING=utf-8`, preservando o resultado real dos testes; não houve alteração de dados ou de testes aprovados para contornar falha.

## Compatibilidade PostgreSQL 18 e resultados efetivos

A primeira tentativa real falhou antes do commit por incompatibilidade da proteção de estrutura com o catálogo do PostgreSQL 18. Os dados dessa tentativa não foram publicados como carga concluída. O [diagnóstico transacional](etapa4_silver/diagnostico_pg18.json) encontrou cinco restrições `NOT NULL` de tipo `n` e uma chave primária por tabela. O carregador antigo esperava somente uma entrada em `pg_constraint`; no PostgreSQL 18 as restrições `NOT NULL` também constam desse catálogo, como documentado em [pg_constraint](https://www.postgresql.org/docs/18/catalog-pg-constraint.html).

A correção desconsidera apenas o tipo `n` na contagem de restrições extras, mantendo a conferência de nulabilidade por coluna, da chave primária técnica, de tipos, ownership e comentários. Restrições adicionais de outros tipos continuam recusadas. A [proteção corrigida passou em transação com rollback](etapa4_silver/compatibilidade_pg18.json) antes da nova carga completa. Não houve relaxamento de regras de negócio ou exclusão de registros para fazer o teste passar.

O parser de SQLSTATE foi ajustado para mensagens localizadas, sem gravar o stderr bruto. Isso permitiu registrar e exigir `22012` na falha deliberada, em vez de considerar qualquer falha genérica como prova de rollback. Há testes para os prefixos de erro em português e inglês.

Na execução final, os 97 campos físicos das nove tabelas foram registrados no catálogo, incluindo os 45 campos técnicos. Todas as verificações de estrutura, originais, nulos, chaves, somas e fingerprints passaram tanto nas cargas quanto na conferência posterior ao rollback. Não foram encontrados erros de conversão. As somas exatas observadas no PostgreSQL foram:

| Campo | Bronze | Silver | Diferença Bronze–Silver |
| --- | ---: | ---: | ---: |
| `price` | 13.591.643,70 | 13.591.643,70 | 0 |
| `freight_value` | 2.251.909,54 | 2.251.909,54 | 0 |
| `payment_value` | 16.008.872,12 | 16.008.872,12 | 0 |

A unicidade das chaves candidatas `order_id`, `order_id + order_item_id` e `order_id + payment_sequential` foi confirmada, sem vazios ou duplicatas. As repetições esperadas de `customer_unique_id`, prefixo geográfico e chaves isoladas de avaliações foram preservadas. As seis referências principais de pedidos, itens, pagamentos e avaliações tiveram zero órfãos. Na relação produtos–tradução permanecem 13 registros sem correspondência, como na Bronze.

A reconciliação independente por pedido reproduziu 98.665 pedidos comparáveis e 303 diferenças absolutas superiores a 0,01, com 264 positivas e 39 negativas. São divergências observadas entre fontes, não erros novos da carga. Não se ajustou qualquer valor para igualar pagamentos a preço e frete.

## Exceções conhecidas que devem permanecer visíveis

As referências abaixo vêm do profiling e do diagnóstico existentes, cujos arquivos e fontes foram preservados:

| Observação | Evidência e comportamento esperado na Silver |
| --- | --- |
| Geolocalização com duplicatas | Manter os 1.000.163 registros, inclusive 261.831 duplicatas exatas excedentes; prefixo de CEP não é chave única |
| Avaliações repetidas por chave isolada | Manter 99.224 registros; `review_id` tem 814 ocorrências excedentes e `order_id`, 551. A combinação é única nesta cópia, sem deduplicação |
| Cliente recorrente na origem | Manter 99.441 registros de clientes e 96.096 identidades distintas, sem escolher localização permanente |
| Ausência de filhos | Preservar 775 pedidos sem itens e um sem pagamento, sem criar linhas artificiais |
| Categorias | Manter 610 categorias de produto vazias e 13 produtos em duas categorias preenchidas sem tradução; a nova leitura de referência confirmou os 13 casos |
| Campos vazios | Manter 160 aprovações, 1.783 datas de transportadora e 2.965 datas de entrega ao cliente ausentes; 87.656 títulos e 58.247 comentários de avaliação vazios; demais nulos detalhados no manifesto de preparação |
| Datas e status | Não corrigir 166 entregas à transportadora anteriores à compra, 23 entregas ao cliente anteriores à transportadora, oito entregues sem data de entrega e seis cancelados com data de entrega |
| Divergências financeiras | Preservar os 303 pedidos com diferença absoluta superior a 0,01, sendo 264 positivas e 39 negativas; não ajustar valores nem chamar pagamento de recebimento |

RN01 preserva todos os pedidos; RN02 não vira filtro de carga; RN03 mantém preço e frete separados; RN04 mantém a semântica limitada de pagamentos; RN05 preserva divergências; RN06 mantém ambas as chaves de cliente; RN07 não é recalculada nem implementada como indicador nesta Silver; RN08 conserva a geolocalização como fonte, sem junção dimensional. Não há criação de membros dimensionais, SCD2 ou regras de rateio.

## Pendências e limites

Conexão, exclusividade, carga, testes de catálogo, comparação integral, reexecução idempotente e rollback foram executados e documentados. Para futuras execuções, permanece necessário verificar espaço temporário no cliente e espaço/transação no servidor: a preparação de COPY e o fingerprint ordenado consomem disco/memória conforme o volume. O arquivo geográfico contém mais de um milhão de registros. A carga estática integral e seus testes não constituem política de atualização incremental ou histórico.

Permanecem pendentes procedência externa, versão publicada, licença, moeda, semântica de valores e causas das exceções. O manifesto identifica a cópia local pelos hashes, sem inventar esses metadados. A versão estática não aceita silenciosamente outra fonte, não instala serviços, preserva os CSVs e a documentação validada de regras e modelagem e não implementa Gold ou consumo analítico.

A carga Silver foi concluída e verificada no escopo descrito. A Etapa 4A não está declarada aprovada.
