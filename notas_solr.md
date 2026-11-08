# Notas Solr (M2)

## 1. Como ligar tudo

A partir da pasta `Projeto`, com o Docker ligado:

```bash
docker start meic_solr               # liga o Solr (mantém os dados)
.venv/bin/python solr/webapp.py      # liga a app; deixar este terminal aberto
```

- App de pesquisa: http://localhost:8000
- Interface do Solr: http://localhost:8983/solr/#/f1/query
- Desligar: `Ctrl+C` no terminal da app e `docker stop meic_solr`
- Se o `meic_solr` não existir: `./solr/startup.sh`
- Se a app der `Address already in use`: já está ligada, basta abrir o link
- Depois de mudar o `queries.json`: reiniciar a app

**App ou interface do Solr?** A app serve para pesquisar como um utilizador e para a
demonstração. A interface do Solr serve para afinar pesos e perceber porque é que um
resultado apareceu. Ambas usam os mesmos dados, e a app precisa do Solr ligado.

---

## 2. O que falta fazer

1. Testar 3 ou 4 necessidades na app. Mudar queries só agora, antes de avaliar.
2. Fazer commit e push, para o grupo avaliar as mesmas listas.
3. Avaliar os 218 documentos: 1 ou 0 na coluna `relevant` de `solr/qrels/N*.csv`.

   | Pessoa | Necessidades | Documentos |
   |---|---|---|
   | A | N1, N11, N13 | 53 |
   | B | N2, N3, N5 | 53 |
   | C | N4, N7, N8 | 52 |
   | D | N6, N9, N10, N12 | 60 |

   - Critérios em `docs/information_needs.md`.
   - Documento do tipo errado leva 0 (por exemplo, um piloto em N4, que pede corridas).
   - Excerto insuficiente: abrir no Solr com `q=id:race_1996_06` e `fl=*`.
   - A avaliação tem de ser feita por nós, não por IA.
4. Correr `.venv/bin/python solr/evaluate.py`.
5. Escrever no relatório: indexação e schema, os dois setups, métricas e análise,
   demonstração e ideias para o M3.
6. Confirmar na página da cadeira: limite de páginas, prazo e se há demonstração ao vivo.

---

## 3. O que está na pasta `solr/`

```
queries.json ──▶ search.py ──▶ results/  (o que cada sistema devolveu)
                     │
                     └───────▶ qrels/    (nós marcamos 1 ou 0)
                                  │
results/ + qrels/ ──▶ evaluate.py ──▶ results/metrics.csv
                                      results/precision_recall.png
```

| O quê | Para que serve | Quem mexe |
|---|---|---|
| `startup.sh` | Cria o Solr do zero: container, schema e 2058 documentos | Corre-se quando muda o schema |
| `schema.json` | Diz o tipo de cada campo e como o texto é processado | Editar à mão |
| `queries.json` | Os dois sistemas (`simple`, `boosted`) e as queries N1 a N13 | Editar à mão |
| `search.py` | Faz as pesquisas e gera `results/` e `qrels/` | Corre-se |
| `qrels/` | Documentos a avaliar, um ficheiro por necessidade | **Nós preenchemos** |
| `results/` | Resultados e métricas | Gerado, não editar |
| `evaluate.py` | Compara `results/` com `qrels/` e calcula as métricas | Corre-se |
| `webapp.py` | Servidor da app de pesquisa | Corre-se |
| `web/` | A página da app (`index.html`, `styles.css`, `app.js`, `favicon.svg`) | Só para mudar o aspeto |
| `README.md` | Guia completo do Solr | Consulta |

### `qrels/` (relevance judgments)

São as respostas certas, marcadas por nós. Há um ficheiro por necessidade (`N1.csv` a
`N13.csv`) com todos os documentos que algum dos sistemas devolveu, sem repetições.

```
id,title,relevant,snippet
race_1996_06,1996 Monaco Grand Prix,1,"..."
```

| Coluna | Significado |
|---|---|
| `id`, `title` | Que documento é |
| `relevant` | **A preencher:** 1 se responde à necessidade, 0 se não responde |
| `snippet` | Excerto com as palavras da query entre `[ ]`, para ajudar a decidir |

Se correr o `search.py` outra vez, as avaliações já feitas mantêm-se e só aparecem
documentos novos por avaliar.

### `results/`

| Ficheiro | Conteúdo |
|---|---|
| `simple.json` | Os 10 primeiros resultados do `simple`, por ordem, para cada necessidade |
| `boosted.json` | O mesmo para o `boosted` |
| `metrics.csv` | P@10 e AP por necessidade, e MAP por sistema. **Está a 0 até haver avaliações** |
| `precision_recall.png` | Gráfico que compara os dois sistemas. **Só é útil depois de avaliar** |

### Métricas

| Métrica | Significado |
|---|---|
| **P@10** | Dos 10 primeiros resultados, que fração é relevante (6 em 10 dá 0.6) |
| **AP** | Premeia ter os relevantes mais acima na lista |
| **MAP** | Média das AP das 13 necessidades: um número por sistema para os comparar |
| **Curva precision-recall** | Como a precisão desce à medida que se encontram mais relevantes |

### Os dois sistemas

| | `simple` (na app: Simple) | `boosted` (na app: Relevance) |
|---|---|---|
| Onde procura | Campo único `all_text`, com todo o texto | Vários campos, cada um com o seu peso |
| Bónus se as palavras aparecem juntas | Não | Sim |
| Filtro por tipo na avaliação | Não | Sim |

---

## 4. Campos da página de pesquisa do Solr

| Campo | O que faz | Exemplo |
|---|---|---|
| **Request-Handler (qt)** | Tipo de pedido; deixar `/select` | `/select` |
| **q** | O que se procura | `safety car` |
| **fq** | Filtra resultados sem afetar a ordem | `type:race` |
| **sort** | Ordena por outro critério que não a relevância | `date asc` |
| **start, rows** | A partir de que resultado e quantos mostrar | `0`, `10` |
| **fl** | Que campos mostrar; `score` mostra a pontuação | `title,score` |
| **df** | Campo usado quando a query não indica nenhum; com `edismax` usa-se o `qf` | `all_text` |
| **Raw Query Parameters** | Parâmetros extra sem caixa própria | `q.op=AND` |
| **wt** | Formato da resposta | `json` |
| **indent off** | Tira a formatação da resposta | desligado |
| **debugQuery** | Explica como cada pontuação foi calculada | marcar para investigar |

Caixas que abrem mais opções: **edismax** (a que usamos), **dismax** (versão mais antiga),
**hl** (destaca as palavras encontradas), **facet** (contagens por categoria), **spatial**
(localização), **spellcheck** (correção ortográfica).

### Opções do edismax

| Campo | O que faz | Exemplo |
|---|---|---|
| **qf** | Onde procurar e quanto vale cada campo | `summary^3 race^2` |
| **pf** | Bónus se as palavras aparecerem juntas | `race^3` |
| **ps** | Distância permitida entre palavras no bónus do `pf` | `3` |
| **pf2, pf3** | Como o `pf`, mas para grupos de 2 ou 3 palavras | `race^2` |
| **ps2, ps3** | Distância permitida para o `pf2` e o `pf3` | `3` |
| **mm** | Quantas palavras da query têm de existir | `2` ou `75%` |
| **qs** | Distância permitida nas frases escritas entre aspas na `q` | `2` |
| **tie** | Quanto contam os outros campos além do melhor (0 a 1) | `0.1` |
| **q.alt** | Query usada se a `q` estiver vazia | `*:*` |
| **bq** | Bónus para documentos que cumprem uma condição | `type:race^2` |
| **bf, boost** | Bónus com uma fórmula (`bf` soma, `boost` multiplica) | `log(wins)` |
| **uf** | Que campos o utilizador pode indicar na query | `title` |
| **stopwords** | Se respeita o filtro de palavras comuns | deixar marcado |
| **lowercaseOperators** | Se `and` e `or` em minúsculas contam como operadores | deixar como está |

Os essenciais para o trabalho: **q, fq, fl, rows, qf, pf, ps, debugQuery**.

### Teste rápido

Em http://localhost:8983/solr/#/f1/query:

- `q` = `rain wet surprise`
- `fq` = `type:race`
- `fl` = `title,score`
- marcar **edismax** e pôr `qf` = `summary^3 race^2 title^2`
- **Execute Query**

---

## 5. Campos dos nossos documentos

**Comuns**

| Campo | Significado |
|---|---|
| `id`, `type` | Identificador e tipo (`race`, `driver`, `team`, `circuit`) |
| `title`, `summary` | Nome e resumo do artigo |
| `word_count` | Número de palavras |
| `wikipedia_url`, `wikipedia_title`, `wikipedia_pageid`, `wikipedia_revid` | Referências ao artigo original |
| `all_text` | Junta todo o texto para o baseline; pesquisa-se, mas não aparece nos resultados |

**Corridas (`race`)**

| Campo | Significado |
|---|---|
| `background`, `qualifying`, `race`, `post_race`, `other` | Texto: antecedentes, qualificação, corrida, depois da corrida, restantes secções |
| `season`, `round`, `date` | Época, ronda e data |
| `circuit`, `circuit_id`, `locality`, `country` | Circuito e local |
| `winner`, `winning_team`, `pole_position`, `podium`, `fastest_lap` | Vencedor, equipa vencedora, pole, pódio, volta mais rápida |
| `starters`, `finishers` | Quantos partiram e quantos terminaram |
| `retirements`, `retirement_reasons` | Quem desistiu e porquê |
| `drivers`, `driver_ids`, `teams`, `team_ids` | Pilotos e equipas participantes |

**Pilotos (`driver`)**

| Campo | Significado |
|---|---|
| `biography` | Texto: biografia |
| `nationality`, `date_of_birth`, `code`, `permanent_number` | Dados pessoais, código (`HAM`) e número |
| `race_starts` | Corridas em que alinhou à partida |
| `teams`, `team_ids` | Equipas por onde passou |

**Equipas (`team`)**

| Campo | Significado |
|---|---|
| `history` | Texto: história |
| `nationality`, `names` | Nacionalidade e nomes usados ao longo do tempo |
| `drivers`, `driver_ids` | Pilotos da equipa |

**Circuitos (`circuit`)**

| Campo | Significado |
|---|---|
| `history`, `layout`, `events`, `other` | Texto: história, traçado, eventos, restantes secções |
| `locality`, `country`, `latitude`, `longitude`, `altitude` | Localização |
| `grands_prix`, `most_wins` | Grandes Prémios ali realizados e quem mais venceu |

**Campos usados em mais do que um tipo**

| Campo | Significado | Tipos |
|---|---|---|
| `first_season`, `last_season`, `seasons` | Primeira, última e lista de épocas | piloto, equipa, circuito |
| `race_entries` | Número de corridas | piloto, equipa, circuito |
| `race_ids` | Ligações às corridas | piloto, equipa, circuito |
| `wins`, `podiums`, `pole_positions` | Vitórias, pódios e poles | piloto, equipa |
| `championships`, `championship_years` | Títulos e anos em que foram ganhos | piloto, equipa |
