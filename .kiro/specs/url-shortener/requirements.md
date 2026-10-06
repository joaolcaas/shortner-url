# Requirements Document

## Introduction

Este documento descreve os requisitos do backend de um encurtador de URLs. O sistema permite que usuários transformem URLs longas em códigos curtos, redireciona visitantes para a URL original e registra dados de acesso para análise (analytics). O backend será construído em Python com o framework Flask. Os dados de encurtamento (mapeamento código → URL) serão armazenados no Redis, enquanto os dados de analytics (registros de cliques) serão armazenados no SQLite. O projeto incluirá testes unitários.

Este documento cobre exclusivamente o backend. Um frontend será adicionado posteriormente e está fora do escopo destes requisitos.

## Glossary

- **Backend**: Serviço HTTP construído em Python com Flask que expõe a API de encurtamento e de analytics.
- **Short_Code**: Código curto de 7 caracteres alfanuméricos (`[A-Za-z0-9]`) que identifica unicamente uma URL encurtada.
- **Short_URL**: URL completa composta pelo domínio base do serviço concatenado com o Short_Code.
- **Original_URL**: URL de destino fornecida pelo usuário no momento do encurtamento.
- **Redis_Store**: Armazenamento Redis que mantém o mapeamento entre Short_Code e os metadados da URL encurtada (Original_URL, data de criação, data de expiração).
- **Analytics_Store**: Banco de dados SQLite que mantém os registros de cliques para fins de análise.
- **Click_Record**: Registro de um acesso ao Short_Code contendo referenciador (referrer), user-agent, endereço IP e timestamp.
- **URL_Validator**: Componente responsável por validar que uma URL fornecida utiliza o esquema `http` ou `https`.
- **Expiration_Date**: Data e hora (campo `expiresAt`) a partir da qual uma URL encurtada deixa de redirecionar.
- **Code_Generator**: Componente responsável por gerar o Short_Code alfanumérico de 7 caracteres.
- **Code_Pattern**: Formato aceito para consulta de um Short_Code recebido em uma requisição, definido como uma sequência de 1 a 16 caracteres alfanuméricos (`[A-Za-z0-9]`).
- **Click_Count**: Quantidade total de Click_Records associados a um Short_Code, representada como um inteiro maior ou igual a 0.
- **Page**: Número da página solicitada na listagem paginada de URLs encurtadas, iniciando em 1.
- **Page_Size**: Quantidade máxima de itens retornados por página na listagem de URLs encurtadas, com valor padrão 50 e máximo 100.

## Requirements

### Requisito 1: Encurtar URL

**User Story:** Como usuário, quero encurtar uma URL longa, para que eu possa compartilhá-la através de um link curto.

#### Acceptance Criteria

1. WHEN uma requisição `POST /api/shorten` é recebida com um corpo contendo um campo `url` com esquema `http` ou `https`, THE Backend SHALL gerar um Short_Code, persistir o mapeamento no Redis_Store e retornar status 201 com um corpo JSON contendo `shortCode`, `shortUrl`, `originalUrl`, `createdAt` e `expiresAt`.
2. THE Code_Generator SHALL gerar um Short_Code composto por 7 caracteres alfanuméricos (`[A-Za-z0-9]`).
3. IF o campo `url` da requisição `POST /api/shorten` utiliza um esquema diferente de `http` ou `https`, ou não possui um host válido, THEN THE Backend SHALL retornar status 400 com uma mensagem de erro indicando que a URL é inválida, sem persistir qualquer mapeamento.
4. IF o campo `url` está ausente ou vazio na requisição `POST /api/shorten`, THEN THE Backend SHALL retornar status 400 com uma mensagem de erro indicando o problema de validação, sem persistir qualquer mapeamento.
5. WHERE o campo `expiresAt` é fornecido na requisição `POST /api/shorten` com um formato de data válido e representando um instante futuro em relação ao horário atual do servidor, THE Backend SHALL persistir a Expiration_Date associada ao Short_Code no Redis_Store.
6. WHEN um Short_Code é gerado, THE Code_Generator SHALL verificar que o Short_Code não corresponde a nenhum Short_Code já existente no Redis_Store, repetindo a geração em no máximo 5 tentativas.
7. IF o campo `expiresAt` é fornecido com um formato de data inválido na requisição `POST /api/shorten`, THEN THE Backend SHALL retornar status 400 com uma mensagem de erro indicando que o formato de data é inválido, sem persistir qualquer mapeamento.
8. IF o campo `expiresAt` é fornecido com um instante igual ou anterior ao horário atual do servidor na requisição `POST /api/shorten`, THEN THE Backend SHALL retornar status 400 com uma mensagem de erro indicando que a data de expiração deve ser futura, sem persistir qualquer mapeamento.
9. IF o Code_Generator não obtém um Short_Code único após 5 tentativas, THEN THE Backend SHALL retornar status 500 com uma mensagem de erro indicando falha na geração do código, sem persistir qualquer mapeamento.

### Requisito 2: Redirecionar para URL original

**User Story:** Como visitante, quero acessar um link curto, para que eu seja redirecionado à URL original.

#### Acceptance Criteria

1. WHEN uma requisição `GET /:code` é recebida e o Short_Code existe no Redis_Store e possui Expiration_Date igual ou posterior ao instante atual, THE Backend SHALL responder com status 301 e o cabeçalho `Location` definido como a Original_URL.
2. IF uma requisição `GET /:code` é recebida e o Short_Code não existe no Redis_Store, THEN THE Backend SHALL retornar status 404 com um corpo de resposta indicando que o código não foi encontrado.
3. IF uma requisição `GET /:code` é recebida e o Short_Code possui uma Expiration_Date anterior ao instante atual, THEN THE Backend SHALL retornar status 410 com um corpo de resposta indicando que o link expirou.
4. IF uma requisição `GET /:code` é recebida e o Short_Code não corresponde ao formato de Short_Code válido (comprimento entre 1 e 16 caracteres alfanuméricos), THEN THE Backend SHALL retornar status 404 com um corpo de resposta indicando que o código é inválido, sem consultar o Redis_Store.
5. WHEN uma requisição `GET /:code` resulta em redirecionamento com status 301, THE Backend SHALL registrar, após o envio da resposta de redirecionamento, um Click_Record no Analytics_Store contendo referrer, user-agent, endereço IP e timestamp.
6. IF o registro do Click_Record no Analytics_Store falha durante uma requisição `GET /:code` que resultou em status 301, THEN THE Backend SHALL concluir o redirecionamento normalmente sem alterar o status 301 e SHALL preservar a resposta já enviada ao visitante.

### Requisito 3: Listar URLs criadas

**User Story:** Como usuário, quero listar os links que foram criados, para que eu possa acompanhar as URLs encurtadas e seus acessos.

#### Acceptance Criteria

1. WHEN uma requisição `GET /api/urls` é recebida, THE Backend SHALL retornar status 200 com uma lista de URLs encurtadas, onde cada item contém os campos `shortCode`, `shortUrl`, `originalUrl`, `createdAt` (data/hora no formato ISO 8601 UTC), `expiresAt` (data/hora no formato ISO 8601 UTC, ou valor nulo quando a URL não possui expiração) e `clickCount` (inteiro maior ou igual a 0).
2. WHEN uma requisição `GET /api/urls` é recebida, THE Backend SHALL ordenar a lista de URLs encurtadas em ordem decrescente pela data de criação (`createdAt`), do mais recente para o mais antigo, e, em caso de empate na data de criação, ordenar de forma decrescente pelo `shortCode`.
3. WHEN uma requisição `GET /api/urls` é recebida sem o query param `page`, THE Backend SHALL assumir `page` igual a 1.
4. WHEN uma requisição `GET /api/urls` é recebida sem o query param `pageSize`, THE Backend SHALL assumir `pageSize` igual a 50.
5. WHEN uma requisição `GET /api/urls` é recebida com os query params `page` e `pageSize` válidos, THE Backend SHALL retornar no máximo `pageSize` URLs encurtadas correspondentes à página `page`, calculando o deslocamento como `(page - 1) * pageSize`.
6. WHEN uma requisição `GET /api/urls` é recebida, THE Backend SHALL incluir na resposta os metadados de paginação `page` (página atual), `pageSize` (tamanho da página), `total` (total de URLs encurtadas existentes) e `totalPages` (número total de páginas).
7. WHERE o query param `pageSize` é fornecido com valor maior que 100, THE Backend SHALL limitar `pageSize` a 100.
8. IF o query param `page` é fornecido com valor não numérico ou menor que 1, THEN THE Backend SHALL retornar status 400 com uma mensagem de erro indicando que o parâmetro `page` é inválido, sem retornar nenhuma lista de URLs.
9. IF o query param `pageSize` é fornecido com valor não numérico ou menor que 1, THEN THE Backend SHALL retornar status 400 com uma mensagem de erro indicando que o parâmetro `pageSize` é inválido, sem retornar nenhuma lista de URLs.
10. WHEN uma requisição `GET /api/urls` é recebida e a página solicitada está além do total de páginas disponíveis, THE Backend SHALL retornar status 200 com uma lista vazia e os metadados de paginação correspondentes.
11. WHEN uma requisição `GET /api/urls` é recebida e não existem URLs encurtadas, THE Backend SHALL retornar status 200 com uma lista vazia e `total` igual a 0.
12. IF a origem de dados das URLs encurtadas ou das informações de cliques está indisponível durante o processamento de uma requisição `GET /api/urls`, THEN THE Backend SHALL retornar status 503 com uma mensagem de erro indicando falha temporária ao recuperar as URLs, sem retornar nenhuma lista parcial.

### Requisito 4: Consultar estatísticas de uma URL

**User Story:** Como usuário, quero consultar as estatísticas de um link curto, para que eu possa analisar o comportamento de acesso.

#### Acceptance Criteria

1. WHEN uma requisição `GET /api/stats/:code` é recebida e o Short_Code existe, THE Backend SHALL retornar status 200 com um corpo JSON contendo `totalClicks` (inteiro maior ou igual a 0), `clicksByDay` (lista) e `topReferrers` (lista).
2. WHEN uma requisição `GET /api/stats/:code` é recebida e o Short_Code existe, THE Backend SHALL calcular `clicksByDay` considerando os Click_Records dos últimos 30 dias contados a partir da data da requisição, ordenados em ordem crescente de data.
3. WHEN uma requisição `GET /api/stats/:code` é recebida e o Short_Code existe, THE Backend SHALL calcular `topReferrers` agregando os Click_Records por referrer e retornar no máximo os 10 referrers com maior número de cliques, ordenados em ordem decrescente de contagem de cliques.
4. IF uma requisição `GET /api/stats/:code` é recebida e o Short_Code não existe, THEN THE Backend SHALL retornar status 404 com um corpo JSON contendo uma mensagem de erro indicando que o Short_Code não foi encontrado.
5. IF uma requisição `GET /api/stats/:code` é recebida e o `code` é vazio ou possui comprimento diferente do Short_Code definido (entre 1 e 16 caracteres alfanuméricos), THEN THE Backend SHALL retornar status 400 com um corpo JSON contendo uma mensagem de erro indicando que o Short_Code é inválido.
6. WHEN uma requisição `GET /api/stats/:code` é recebida e o Short_Code existe mas não possui Click_Records, THE Backend SHALL retornar status 200 com `totalClicks` igual a 0 e `clicksByDay` e `topReferrers` como listas vazias.

### Requisito 5: Validação de URL

**User Story:** Como operador do sistema, quero que apenas URLs com esquemas seguros sejam aceitas, para que o serviço não encurte endereços inválidos ou maliciosos.

#### Acceptance Criteria

1. WHEN uma URL é submetida para encurtamento e seu esquema é `http` ou `https`, THE URL_Validator SHALL aceitar a URL para processamento.
2. IF uma URL submetida para encurtamento utiliza um esquema diferente de `http` ou `https`, THEN THE URL_Validator SHALL rejeitar a URL e retornar uma indicação de erro informando que o esquema não é suportado, sem armazenar a URL.
3. IF uma URL submetida para encurtamento está vazia, é nula ou não contém um host válido (ausência de domínio após o esquema), THEN THE URL_Validator SHALL rejeitar a URL e retornar uma indicação de erro informando que a URL é inválida, sem armazenar a URL.

### Requisito 6: Persistência de dados

**User Story:** Como operador do sistema, quero que os dados de encurtamento e de analytics sejam armazenados de forma apropriada, para que o serviço opere de forma confiável.

#### Acceptance Criteria

1. WHEN uma URL encurtada é criada, THE Backend SHALL armazenar no Redis_Store o mapeamento entre o Short_Code e os metadados da URL encurtada (URL original, data de criação e, quando aplicável, Expiration_Date) em até 500 milissegundos.
2. IF a gravação do mapeamento no Redis_Store falha, THEN THE Backend SHALL rejeitar a operação de encurtamento, não retornar um Short_Code válido e retornar uma mensagem de erro indicando que a URL não pôde ser persistida.
3. WHEN um redirecionamento é processado com sucesso, THE Backend SHALL registrar o Click_Record correspondente no Analytics_Store em até 1000 milissegundos.
4. IF a gravação do Click_Record no Analytics_Store falha, THEN THE Backend SHALL concluir o redirecionamento normalmente e preservar o estado do Redis_Store sem alteração.
5. WHERE uma Expiration_Date está associada a um Short_Code, WHEN um redirecionamento é solicitado e a data e hora atuais são iguais ou posteriores à Expiration_Date, THE Backend SHALL recusar o redirecionamento e retornar uma mensagem de erro indicando que o Short_Code está expirado.

### Requisito 7: Testes unitários

**User Story:** Como desenvolvedor, quero que o backend possua testes unitários, para que eu possa verificar o comportamento correto das funcionalidades.

#### Acceptance Criteria

1. THE Backend SHALL incluir testes unitários que cobrem a geração de Short_Code, a validação de URL, o encurtamento, o redirecionamento, o registro de cliques, a listagem de URLs e o cálculo de estatísticas, com cada função principal possuindo ao menos um caso de sucesso e um caso de erro.
2. WHEN os testes unitários são executados, THE conjunto de testes SHALL validar os códigos de status esperados para os cenários de sucesso e de erro de cada endpoint.
3. WHEN o conjunto de testes é executado, THE conjunto de testes SHALL reportar o resultado (aprovado ou reprovado) de cada caso de teste de forma observável.
