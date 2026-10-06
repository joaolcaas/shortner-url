# Implementation Plan: Encurtador de URLs (Backend)

## Overview

O plano implementa o backend Flask de forma incremental e orientada a testes, seguindo a arquitetura em camadas do design (rotas → serviços → repositórios) com componentes de apoio puros (validadores e gerador de código). Começa pela estrutura do projeto e pelos componentes de domínio puros (os mais fáceis de testar por propriedades), avança para os repositórios (Redis e SQLite), depois para os serviços e, por fim, conecta tudo às rotas Flask na fábrica da aplicação. Cada tarefa constrói sobre as anteriores e termina com a integração via rotas, sem código órfão.

Linguagem de implementação: **Python** (definida no design). Testes com **pytest** + **Hypothesis**, usando **fakeredis** e **SQLite em memória**. Os testes unitários e de propriedade ficam concentrados ao final, conforme solicitado.

## Tasks

- [x] 1. Preparar estrutura do projeto e dependências
  - Criar a pasta `backend/` com o layout de módulos definido no design: `app.py`, `config.py`, `requirements.txt`, `url_shortener/` (com `routes/`, `services/`, `repositories/`, `domain/`, `pagination.py`) e `tests/`, incluindo todos os arquivos `__init__.py`
  - Preencher `requirements.txt` com as dependências: `flask`, `redis`, `pytest`, `hypothesis`, `fakeredis` (SQLite via `sqlite3` da stdlib)
  - Definir `config.py` com as chaves de configuração `BASE_URL`, `REDIS_URL` e `SQLITE_PATH`
  - _Requirements: 6.1, 7.1_

- [ ] 2. Implementar modelos de domínio e erros
  - [x] 2.1 Definir dataclasses de domínio em `url_shortener/domain/models.py`
    - Criar `UrlMapping`, `ClickRecord`, `DayCount`, `ReferrerCount` e `PaginatedResult` conforme a seção Data Models (todos `frozen=True`, datas em UTC)
    - _Requirements: 1.1, 2.5, 3.1, 4.1_

  - [x] 2.2 Definir erros de domínio em `url_shortener/domain/errors.py`
    - Criar `ValidationError`, `NotFoundError`, `InvalidCodeError`, `GoneError`, `CodeGenerationError`, `PersistenceError` e `DataSourceError`
    - _Requirements: 1.3, 1.9, 2.2, 2.3, 2.4, 3.12, 6.2_

- [x] 3. Implementar validadores de domínio (`domain/validators.py`)
  - [x] 3.1 Implementar `validate_url`
    - Aceitar apenas esquema `http`/`https` (case-insensitive) e exigir host; normalizar e retornar a URL em caso de sucesso; lançar `ValidationError` para URL vazia/nula/sem host ou esquema não suportado
    - _Requirements: 1.1, 1.3, 1.4, 5.1, 5.2, 5.3_

  - [x] 3.2 Implementar `validate_code_pattern`
    - Retornar `True` somente para codes que casam com `[A-Za-z0-9]{1,16}` (Code_Pattern)
    - _Requirements: 2.4, 4.5_

  - [x] 3.3 Implementar `parse_expires_at`
    - Retornar `None` quando ausente; fazer parse ISO 8601; lançar `ValidationError` para formato inválido ou instante `<= now`
    - _Requirements: 1.5, 1.7, 1.8_

  - [x] 3.4 Implementar `parse_pagination`
    - Aplicar defaults (`page=1`, `pageSize=50`), limitar `pageSize` a 100; lançar `ValidationError` para `page`/`pageSize` não numérico ou `< 1`
    - _Requirements: 3.3, 3.4, 3.7, 3.8, 3.9_

- [x] 4. Implementar o gerador de código (`domain/code_generator.py`)
  - [x] 4.1 Implementar `generate_code` e `generate_unique_code`
    - `generate_code`: gerar 7 caracteres de `[A-Za-z0-9]` usando fonte aleatória injetável
    - `generate_unique_code(exists, rng)`: repetir até `exists(code)` ser `False`, no máximo 5 tentativas; lançar `CodeGenerationError` se todas colidirem
    - _Requirements: 1.2, 1.6, 1.9_

- [x] 5. Implementar o cálculo de paginação (`url_shortener/pagination.py`)
  - [x] 5.1 Implementar o utilitário de paginação
    - Calcular `offset = (page - 1) * pageSize`, aplicar o recorte sobre a lista ordenada e montar `PaginatedResult` com `total` e `totalPages = ceil(total / pageSize)`; retornar lista vazia quando a página excede o total
    - _Requirements: 3.5, 3.6, 3.10_

- [ ] 6. Checkpoint - garantir que os componentes de domínio estão consistentes
  - Garantir que todos os testes passam; perguntar ao usuário caso surjam dúvidas.

- [x] 7. Implementar o repositório de URLs no Redis (`repositories/url_repository.py`)
  - [x] 7.1 Implementar `UrlRepository`
    - Implementar `exists`, `save_mapping` (Hash `url:{shortCode}` + índice `urls:index` por epoch de `createdAt`; lançar `PersistenceError` em falha), `get_mapping` (retornar `None` se ausente) e `list_mappings` (lançar `DataSourceError` em indisponibilidade); persistir `createdAt`/`expiresAt` em ISO 8601 UTC
    - _Requirements: 1.1, 3.12, 6.1, 6.2_

- [x] 8. Implementar o repositório de analytics no SQLite (`repositories/analytics_repository.py`)
  - [x] 8.1 Implementar `AnalyticsRepository`
    - Criar o schema `clicks` (com índices `idx_clicks_code` e `idx_clicks_code_time`); implementar `record_click`, `count_clicks`, `count_clicks_bulk`, `clicks_by_day(code, since)` (crescente por data) e `top_referrers(code, limit=10)` (decrescente por contagem)
    - _Requirements: 2.5, 4.2, 4.3, 6.3_

- [x] 9. Implementar o serviço de encurtamento (`services/shorten_service.py`)
  - [x] 9.1 Implementar `ShortenService`
    - Orquestrar `validate_url` → `parse_expires_at` → `generate_unique_code` → montar `UrlMapping` (`createdAt = now` UTC) → `save_mapping`; propagar erros de domínio (`ValidationError`, `CodeGenerationError`, `PersistenceError`)
    - _Requirements: 1.1, 1.5, 1.6, 1.9, 6.2_

- [x] 10. Implementar o serviço de redirecionamento (`services/redirect_service.py`)
  - [x] 10.1 Implementar `RedirectService`
    - Validar o Code_Pattern antes de qualquer I/O (lançar `InvalidCodeError` sem consultar o Redis); buscar o mapeamento (`NotFoundError` se ausente); verificar expiração (`GoneError` se `expiresAt < now`); retornar a `originalUrl`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 6.5_

- [x] 11. Implementar o serviço de listagem (`services/list_service.py`)
  - [x] 11.1 Implementar `ListService`
    - Obter os mapeamentos, ordenar de forma decrescente por `createdAt` e, em empate, decrescente por `shortCode`; aplicar paginação; enriquecer cada item com `clickCount` via `count_clicks_bulk`; montar os itens com todos os campos exigidos; converter indisponibilidade em `DataSourceError`
    - _Requirements: 3.1, 3.2, 3.5, 3.6, 3.11, 3.12_

- [x] 12. Implementar o serviço de estatísticas (`services/stats_service.py`)
  - [x] 12.1 Implementar `StatsService`
    - Validar o Code_Pattern (`ValidationError` → 400) e a existência do code (`NotFoundError` → 404); calcular `totalClicks`, `clicksByDay` (últimos 30 dias, crescente) e `topReferrers` (máx. 10, decrescente); retornar listas vazias e `totalClicks=0` quando não há cliques
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [ ] 13. Checkpoint - garantir que a camada de serviços está consistente
  - Garantir que todos os testes passam; perguntar ao usuário caso surjam dúvidas.

- [ ] 14. Implementar as rotas e a fábrica da aplicação (integração)
  - [x] 14.1 Implementar a rota de encurtamento (`routes/shorten.py`)
    - `POST /api/shorten`: extrair o corpo, chamar `ShortenService`, retornar 201 com `shortCode`, `shortUrl`, `originalUrl`, `createdAt`, `expiresAt`; mapear `ValidationError` → 400, `CodeGenerationError`/`PersistenceError` → 500
    - _Requirements: 1.1, 1.3, 1.4, 1.7, 1.8, 1.9, 6.2_

  - [x] 14.2 Implementar a rota de redirecionamento (`routes/redirect.py`)
    - `GET /:code`: chamar `RedirectService`, responder 301 com `Location`; mapear `InvalidCodeError`/`NotFoundError` → 404 e `GoneError` → 410; após a resposta, chamar `record_click` (referrer, user-agent, IP, timestamp) dentro de try/except que apenas registra log, preservando o 301
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.4, 6.5_

  - [x] 14.3 Implementar a rota de listagem (`routes/urls.py`)
    - `GET /api/urls`: chamar `parse_pagination` e `ListService`, retornar 200 com `items` e metadados (`page`, `pageSize`, `total`, `totalPages`); mapear `ValidationError` → 400 e `DataSourceError` → 503
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12_

  - [x] 14.4 Implementar a rota de estatísticas (`routes/stats.py`)
    - `GET /api/stats/:code`: chamar `StatsService`, retornar 200 com `totalClicks`, `clicksByDay`, `topReferrers`; mapear `ValidationError` → 400 e `NotFoundError` → 404
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ] 14.5 Implementar a fábrica da aplicação e o error handler global (`app.py`)
    - Implementar `create_app` conectando config, clientes (Redis/SQLite), repositórios, serviços e registrando os blueprints de rotas; adicionar `@app.errorhandler` que converte erros de domínio não tratados em JSON `{ "error": "<mensagem>" }` com o status apropriado
    - _Requirements: 1.3, 2.2, 3.12, 6.2_

- [ ] 15. Configurar as fixtures de teste (`tests/conftest.py`)
  - [ ] 15.1 Criar as fixtures de teste
    - Prover fixtures de `app` (via `create_app`), cliente Flask, `fakeredis` e conexão SQLite em memória com o schema criado por teste; configurar `@settings(max_examples=100)` do Hypothesis como padrão dos testes de propriedade
    - _Requirements: 7.1, 7.3_

- [ ] 16. Escrever testes do gerador de código e dos validadores
  - [ ]* 16.1 Escrever teste de propriedade do formato do Short_Code (`tests/test_code_generator.py`)
    - **Property 1: Short_Code sempre tem 7 caracteres alfanuméricos**
    - **Validates: Requirements 1.2**

  - [ ]* 16.2 Escrever teste de propriedade de unicidade e saturação do gerador (`tests/test_code_generator.py`)
    - **Property 2: Geração de código único evita colisões e sinaliza saturação**
    - **Validates: Requirements 1.6, 1.9**

  - [ ]* 16.3 Escrever teste de propriedade de URLs aceitas (`tests/test_validators.py`)
    - **Property 3: URLs http/https com host são aceitas**
    - **Validates: Requirements 1.1, 5.1**

  - [ ]* 16.4 Escrever teste de propriedade de URLs rejeitadas (`tests/test_validators.py`)
    - **Property 4: URLs com esquema não suportado ou sem host são rejeitadas**
    - **Validates: Requirements 1.3, 1.4, 5.2, 5.3**

  - [ ]* 16.5 Escrever teste de propriedade de `expiresAt` inválido/não futuro (`tests/test_validators.py`)
    - **Property 5: expiresAt inválido ou não futuro é rejeitado**
    - **Validates: Requirements 1.7, 1.8**

  - [ ]* 16.6 Escrever testes de exemplo dos validadores e do gerador
    - Casos de sucesso/erro: `url` vazia/None/espaços (Req 1.4), colisão simulada no gerador
    - _Requirements: 1.4, 7.1, 7.2_

- [ ] 17. Escrever testes de encurtamento (`tests/test_shorten.py`)
  - [ ]* 17.1 Escrever teste de propriedade de round-trip encurtar → redirecionar
    - **Property 6: Round-trip encurtar → redirecionar preserva a URL original**
    - **Validates: Requirements 1.1, 1.5, 2.1**

  - [ ]* 17.2 Escrever teste de propriedade de falha de persistência no Redis
    - **Property 21: Falha de persistência no Redis rejeita o encurtamento**
    - **Validates: Requirements 6.2**

  - [ ]* 17.3 Escrever testes de exemplo do endpoint de encurtamento
    - 201 em sucesso; 400 por `url` vazia (Req 1.4); 500 por falha de geração/persistência (Req 1.9, 6.2)
    - _Requirements: 1.1, 1.4, 1.9, 6.2, 7.2_

- [ ] 18. Escrever testes de redirecionamento e registro de clique (`tests/test_redirect.py`)
  - [ ]* 18.1 Escrever teste de propriedade de códigos inexistentes/inválidos
    - **Property 7: Códigos inexistentes ou inválidos no redirecionamento**
    - **Validates: Requirements 2.2, 2.4**

  - [ ]* 18.2 Escrever teste de propriedade de códigos expirados
    - **Property 8: Códigos expirados retornam 410**
    - **Validates: Requirements 2.3, 6.5**

  - [ ]* 18.3 Escrever teste de propriedade de registro de clique
    - **Property 9: Redirecionamento registra o clique com os dados da requisição**
    - **Validates: Requirements 2.5**

  - [ ]* 18.4 Escrever teste de propriedade de resiliência a falha no registro
    - **Property 10: Falha ao registrar o clique não altera o redirecionamento**
    - **Validates: Requirements 2.6, 6.4**

  - [ ]* 18.5 Escrever testes de exemplo do endpoint de redirecionamento
    - Exemplos de 404 (code inexistente) e 410 (code expirado); spy confirmando que o Redis não é consultado para code inválido
    - _Requirements: 2.2, 2.3, 2.4, 7.2_

- [ ] 19. Escrever testes de listagem (`tests/test_urls.py`)
  - [ ]* 19.1 Escrever teste de propriedade da estrutura dos itens
    - **Property 11: Itens da listagem contêm todos os campos exigidos**
    - **Validates: Requirements 3.1**

  - [ ]* 19.2 Escrever teste de propriedade da ordenação
    - **Property 12: A listagem é ordenada por createdAt e shortCode decrescentes**
    - **Validates: Requirements 3.2**

  - [ ]* 19.3 Escrever teste de propriedade do recorte de paginação
    - **Property 13: A paginação corresponde ao recorte da lista ordenada**
    - **Validates: Requirements 3.5, 3.10**

  - [ ]* 19.4 Escrever teste de propriedade do limite de `pageSize`
    - **Property 14: pageSize é limitado a 100**
    - **Validates: Requirements 3.7**

  - [ ]* 19.5 Escrever teste de propriedade dos metadados de paginação
    - **Property 15: Metadados de paginação são consistentes**
    - **Validates: Requirements 3.6**

  - [ ]* 19.6 Escrever teste de propriedade de parâmetros inválidos
    - **Property 16: Parâmetros de paginação inválidos são rejeitados**
    - **Validates: Requirements 3.8, 3.9**

  - [ ]* 19.7 Escrever testes de exemplo do endpoint de listagem
    - Defaults (`page=1`, `pageSize=50` — Req 3.3, 3.4); lista vazia (`items=[]`, `total=0` — Req 3.11); 503 via mock que lança `DataSourceError` (Req 3.12)
    - _Requirements: 3.3, 3.4, 3.11, 3.12, 7.2_

- [ ] 20. Escrever testes de estatísticas (`tests/test_stats.py`)
  - [ ]* 20.1 Escrever teste de propriedade da estrutura das estatísticas
    - **Property 17: Estatísticas de código existente possuem a estrutura exigida**
    - **Validates: Requirements 4.1, 4.6**

  - [ ]* 20.2 Escrever teste de propriedade de `clicksByDay`
    - **Property 18: clicksByDay cobre os últimos 30 dias em ordem crescente**
    - **Validates: Requirements 4.2**

  - [ ]* 20.3 Escrever teste de propriedade de `topReferrers`
    - **Property 19: topReferrers agrega corretamente e limita a 10**
    - **Validates: Requirements 4.3**

  - [ ]* 20.4 Escrever teste de propriedade de code inexistente/inválido
    - **Property 20: Estatísticas de código inexistente ou inválido**
    - **Validates: Requirements 4.4, 4.5**

  - [ ]* 20.5 Escrever testes de exemplo do endpoint de estatísticas
    - Code existente sem cliques → `totalClicks=0` e listas vazias (Req 4.6)
    - _Requirements: 4.6, 7.2_

- [ ] 21. Checkpoint final - garantir que todos os testes passam
  - Garantir que todos os testes passam; perguntar ao usuário caso surjam dúvidas.

## Notes

- As subtarefas marcadas com `*` são opcionais (testes unitários, de propriedade e de integração) e podem ser puladas para um MVP mais rápido.
- Cada tarefa referencia requisitos específicos para rastreabilidade; os testes de propriedade referenciam explicitamente a propriedade do design que validam.
- Os testes de propriedade usam Hypothesis com no mínimo 100 iterações (`@settings(max_examples=100)`); os testes de exemplo cobrem edge cases e condições de erro; `fakeredis` e SQLite em memória isolam o I/O.
- Os checkpoints garantem validação incremental ao fim de cada bloco (domínio, serviços e integração completa).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["3.1", "3.2", "3.3", "3.4", "4.1", "5.1"] },
    { "id": 3, "tasks": ["7.1", "8.1"] },
    { "id": 4, "tasks": ["9.1", "10.1", "11.1", "12.1"] },
    { "id": 5, "tasks": ["14.1", "14.2", "14.3", "14.4"] },
    { "id": 6, "tasks": ["14.5"] },
    { "id": 7, "tasks": ["15.1"] },
    { "id": 8, "tasks": ["16.1", "16.2", "16.3", "16.4", "16.5", "16.6", "17.1", "17.2", "17.3", "18.1", "18.2", "18.3", "18.4", "18.5", "19.1", "19.2", "19.3", "19.4", "19.5", "19.6", "19.7", "20.1", "20.2", "20.3", "20.4", "20.5"] }
  ]
}
```
