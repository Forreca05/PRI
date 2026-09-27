# F1 Search — PRI 2026/27

Sistema de pesquisa sobre **corridas, pilotos e equipas de Fórmula 1**. Junta duas
fontes de dados distintas:

| Fonte | Tipo | O que dá |
|---|---|---|
| [Jolpica F1](https://github.com/jolpica/jolpica-f1) (sucessora da Ergast API) | **estruturada** (CSV) | resultados, grelhas, abandonos, títulos, equipas… desde 1950 |
| [Wikipedia (EN)](https://en.wikipedia.org) | **texto** (artigos) | a narrativa de cada corrida, biografia de cada piloto, história de cada equipa |

A **ligação** entre as duas é o link da Wikipedia que a própria Jolpica guarda para
cada corrida, piloto e equipa.

**Coleção final: 1982 documentos** (1116 corridas, 719 pilotos, 147 equipas),
2,65 milhões de palavras, vocabulário de 32 502 termos.

---

## Índice

1. [Como correr](#1-como-correr)
2. [Estrutura das pastas](#2-estrutura-das-pastas)
3. [Fluxo dos dados](#3-fluxo-dos-dados)
4. [O pipeline, passo a passo](#4-o-pipeline-passo-a-passo)
5. [Modelo conceptual](#5-modelo-conceptual)
6. [Os documentos](#6-os-documentos)
7. [Números da coleção](#7-números-da-coleção)
8. [Problemas de qualidade encontrados](#8-problemas-de-qualidade-encontrados)
9. [Decisões tomadas (e porquê)](#9-decisões-tomadas-e-porquê)

---

## 1. Como correr

```bash
cd pipeline
make
```

Isto cria o ambiente virtual (`../.venv`), instala as dependências e corre os 5
passos por ordem. Com os dados já descarregados demora ~1,5 min; do zero demora
~10 min (por causa da Wikipedia).

Cada passo também pode correr sozinho:

| Comando | O que faz |
|---|---|
| `make collect` | passo 1 — descarrega os dados da Jolpica |
| `make structure` | passo 2 — constrói corridas, pilotos e equipas |
| `make wikipedia` | passo 3 — descarrega os artigos da Wikipedia |
| `make documents` | passo 4 — constrói a coleção final |
| `make analyze` | passo 5 — estatísticas e gráficos |
| `make clean` | apaga tudo o que é gerado, **mantém** os downloads |
| `make clean-all` | apaga também os downloads (o próximo `make` descarrega tudo de novo) |

---

## 2. Estrutura das pastas

```
Projeto/
├── README.md
├── .gitignore                 ← ignora .venv/ e data/raw/
├── pipeline/                  ← TODO o código
│   ├── makefile               ← corre os passos por ordem
│   ├── requirements.txt
│   ├── utils.py               ← caminhos, constantes (ex.: MIN_WORDS = 100), ler/escrever JSON
│   ├── collect_structured.py  ← passo 1
│   ├── build_structured.py    ← passo 2
│   ├── collect_wikipedia.py   ← passo 3
│   ├── wikitext.py            ← converte wikitext em texto limpo (usado no passo 4)
│   ├── build_documents.py     ← passo 4
│   └── analyze.py             ← passo 5
└── data/
    ├── raw/                   ← dados ORIGINAIS, nunca alterados
    │   ├── jolpica/           ← 11 CSVs + metadata.json (que versão do dump foi usada)
    │   └── wikipedia/         ← race/, driver/, team/ — um JSON por artigo
    ├── interim/               ← resultados intermédios e registos de decisões
    │   ├── races_structured.json
    │   ├── drivers_structured.json
    │   ├── teams_structured.json
    │   ├── rejected_documents.json   ← o que foi excluído e porquê
    │   └── section_mapping.json      ← que secção da Wikipedia foi para que campo
    ├── processed/
    │   └── documents.json     ← ★ A COLEÇÃO FINAL (é isto que vai para o Solr no M2)
    └── analysis/
        ├── stats.json         ← todos os números para o relatório
        └── *.png              ← 9 gráficos
```

**Porquê separar `raw` / `interim` / `processed`?** O `raw` nunca é modificado:
qualquer passo pode ser refeito a partir dele, o que torna o pipeline
**reprodutível**. O `interim` guarda as decisões tomadas (o que foi rejeitado, como
as secções foram mapeadas), para poderem ser justificadas no relatório.

---

## 3. Fluxo dos dados

```
                     1. collect_structured
 JOLPICA (dump CSV) ───────────────────────► raw/jolpica/*.csv
                                                   │
                                                   ▼
                                          2. build_structured
                                  (junta tabelas; agrupa equipas)
                                                   │
                       interim/{races,drivers,teams}_structured.json
                                  │   (cada registo tem o link da Wikipedia)
                                  ▼
 WIKIPEDIA (API) ◄──── 3. collect_wikipedia ───► raw/wikipedia/{race,driver,team}/*.json
                       (lotes de 20; resolve páginas de desambiguação)
                                  │
                                  ▼
                        4. build_documents
     (wikitext → texto; secções → campos; filtro ≥ 100 palavras; ligações)
                                  │
                                  ▼
                       processed/documents.json
                                  │
                                  ▼
                   5. analyze ──► analysis/stats.json + gráficos
```

---

## 4. O pipeline, passo a passo

### Passo 1 — `collect_structured.py`: fonte estruturada

- Descarrega o **dump oficial da Jolpica** (um zip com um CSV por tabela da base de
  dados) e guarda só as 11 tabelas necessárias.
- **Porquê o dump e não a API?** A API obrigaria a ~260 pedidos paginados, com
  limite de pedidos por hora. O dump é um único download.
- O link do dump aponta sempre para a versão mais recente, por isso o script regista
  em `raw/jolpica/metadata.json` qual versão foi usada (atualmente a de 2026‑09‑12).

### Passo 2 — `build_structured.py`: juntar as tabelas

A Jolpica é uma base de dados relacional. O script faz os *joins* para chegar a um
registo por corrida, por piloto e por equipa:

```
season ─< round ─< session (tipo 'R' = corrida) ─< sessionentry   (um resultado)
round  ─< roundentry >─ teamdriver >─ driver
                                  └─> team
```

- **Corrida**: vencedor, pole, pódio, volta mais rápida, nº de partidas e de
  chegadas, abandonos com motivo (`"Sergio Pérez: Engine"`), pilotos e equipas.
- **Piloto**: vitórias, pódios, poles, títulos (e anos), equipas, épocas.
- **Equipa**: o mesmo, com títulos de **construtores**.
- **Equipas agrupadas**: a Jolpica tem uma linha por combinação chassis‑motor
  ("Cooper", "Cooper‑Climax", "Cooper‑Maserati"…), e várias apontam para o mesmo
  artigo. Cada equipa da coleção corresponde a **um artigo**, com a lista de nomes
  em `names`. O nome escolhido é o que não tem motor ("McLaren", não "McLaren‑Ford").
- Só entram corridas que **já aconteceram**; o título de 2026 (época a decorrer) não
  é contado.
- **Validação**: os números batem com os factos conhecidos (Senna 41 vitórias,
  65 poles, 3 títulos; Schumacher 91 vitórias, 7 títulos; Ferrari 16 títulos de
  construtores; McLaren 10; Williams 9).

### Passo 3 — `collect_wikipedia.py`: fonte textual

- Para cada registo, usa o link da Wikipedia e descarrega o artigo em **wikitext**
  (o texto-fonte da Wikipedia), mais o `pageid` e o `revid` (a versão exata).
- **Lotes de 20 artigos por pedido** (~110 pedidos em vez de ~2150): a Wikipedia
  bloqueia clientes anónimos que fazem um pedido por página (HTTP 429). O script
  também espera o tempo que o servidor pede (`Retry-After`).
- **Cache**: cada artigo fica num ficheiro em `raw/wikipedia/`. Voltar a correr só
  descarrega o que falta.
- **Páginas de desambiguação**: alguns links da Jolpica levam a páginas do tipo
  *"Tony Brooks may refer to…"*. O script deteta-as e escolhe a entrada certa, por
  esta ordem de prioridade:
  1. link cujo título menciona "Formula One" ou "racing driver";
  2. link numa linha que menciona "Formula One";
  3. link numa linha que menciona "racing" / "race car".

  A correção fica registada no ficheiro (`disambiguation_resolved_from`).

### Passo 4 — `build_documents.py` + `wikitext.py`: a coleção

1. **Wikitext → texto limpo** (`wikitext.py`, com a biblioteca `mwparserfromhell`):
   - remove tabelas, referências, infoboxes, imagens, categorias, comentários;
   - troca links pelo texto visível (`[[Scuderia Ferrari|Ferrari]]` → "Ferrari");
   - mantém o texto de templates que fazem parte da frase
     (`{{convert|5.1|km}}` → "5.1 km").
2. **Secções → campos fixos**: cada artigo é partido pelas secções (`== Race ==`)
   e cada secção é mapeada por palavras-chave para um campo:

   | Tipo | Campos de texto |
   |---|---|
   | race | `summary` (introdução), `background`, `qualifying`, `race`, `post_race`, `other` |
   | driver | `summary`, `biography` |
   | team | `summary`, `history` |

   Secções sem prosa (References, Classification, Championship standings, Racing
   record…) são descartadas **com as suas subsecções**. Uma subsecção "Post-race"
   dentro de "Race" vai para `post_race`.
3. **Filtro de qualidade**: documentos com **menos de 100 palavras** de texto são
   rejeitados, tal como artigos inexistentes ou repetidos. Tudo fica em
   `interim/rejected_documents.json` com o motivo.
4. **Ligações**: corridas ↔ pilotos ↔ equipas, nos dois sentidos, só entre
   documentos que existem na coleção.

### Passo 5 — `analyze.py`: caracterização

Gera `analysis/stats.json` e os gráficos:

| Gráfico | Mostra |
|---|---|
| `word_count_distribution.png` | tamanho dos documentos, por tipo |
| `race_words_by_decade.png` | quantidade de texto por década |
| `race_field_coverage.png` | % de corridas com cada campo preenchido |
| `zipf.png` | frequência vs. posição dos termos (lei de Zipf) |
| `heaps.png` | crescimento do vocabulário (lei de Heaps) |
| `top_terms.png` | termos mais frequentes por tipo (sem stopwords) |
| `retirement_reasons.png` | motivos de abandono mais comuns |
| `driver_nationalities.png` | nacionalidades dos pilotos |
| `race_countries.png` | corridas por país |

---

## 5. Modelo conceptual

```
        ┌──────────┐    participa em (N:M)    ┌──────────┐
        │  Driver  │◄────────────────────────►│   Race   │
        └────┬─────┘  (grelha, posição,        └────┬─────┘
             │         motivo de abandono)          │
             │ correu por (N:M)                     │ teve (N:M)
             ▼                                      ▼
        ┌──────────┐                                │
        │   Team   │◄───────────────────────────────┘
        └──────────┘
```

No JSON, as relações são listas de ids:

| Documento | Liga a |
|---|---|
| race | `driver_ids`, `team_ids` |
| driver | `race_ids`, `team_ids` |
| team | `race_ids`, `driver_ids` |

---

## 6. Os documentos

Todos os documentos estão em `data/processed/documents.json`. Cada um tem:

- **campos estruturados** (da Jolpica) — para filtros e *boosts* no Solr;
- **campos de texto** (da Wikipedia) — o que é pesquisado;
- `word_count`, `wikipedia_url`, `wikipedia_title`, `wikipedia_pageid`, `wikipedia_revid`.

### race — id `race_<época>_<ronda>`

| Campo | Exemplo (`race_2021_22`) |
|---|---|
| `title` | 2021 Abu Dhabi Grand Prix |
| `season`, `round`, `date` | 2021, 22, 2021-12-12 |
| `circuit`, `locality`, `country` | Yas Marina Circuit, Abu Dhabi, UAE |
| `winner`, `winning_team` | [Max Verstappen], [Red Bull] |
| `pole_position`, `podium`, `fastest_lap` | [Max Verstappen], [Verstappen, Hamilton, Sainz], [Max Verstappen] |
| `starters`, `finishers` | 19, 14 |
| `retirements`, `retirement_reasons` | ["Sergio Pérez: Engine", …], [Accident, Brakes, Engine, Gearbox] |
| `drivers`, `driver_ids`, `teams`, `team_ids` | ligações |
| **texto** | `summary`, `background`, `qualifying`, `race`, `post_race`, `other` |

### driver — id `driver_<referência>`

| Campo | Exemplo (`driver_hamilton`) |
|---|---|
| `title`, `nationality`, `date_of_birth` | Lewis Hamilton, British, 1985-01-07 |
| `code`, `permanent_number` | HAM, 44 |
| `first_season`, `last_season`, `seasons` | 2007, 2026, [2007 … 2026] |
| `teams`, `team_ids` | [McLaren, Mercedes, Ferrari] |
| `race_entries`, `race_starts` | 393, 393 |
| `wins`, `podiums`, `pole_positions` | 106, 207, 104 |
| `championships`, `championship_years` | 7, [2008, 2014, 2015, 2017, 2018, 2019, 2020] |
| `race_ids` | ligações |
| **texto** | `summary`, `biography` |

### team — id `team_<referência>`

| Campo | Exemplo (`team_cooper`) |
|---|---|
| `title`, `nationality` | Cooper, British |
| `names` | [Cooper, Cooper-Climax, Cooper-Maserati, … 11 nomes] |
| `first_season`, `last_season` | 1950, 1969 |
| `race_entries`, `wins`, `podiums`, `pole_positions` | 129, 16, 59, 10 |
| `championships`, `championship_years` | 2, [1959, 1960] (construtores) |
| `drivers`, `driver_ids`, `race_ids` | ligações |
| **texto** | `summary`, `history` |

---

## 7. Números da coleção

| | Corridas | Pilotos | Equipas | Total |
|---|---|---|---|---|
| Registos na Jolpica | 1162 | 818 | 168 | 2148 |
| **Aceites** | **1116** | **719** | **147** | **1982** |
| Rejeitados | 46 | 99 | 21 | 166 |
| Palavras por documento (mediana) | 827 | 690 | 1082 | |
| Palavras por documento (média) | 1252 | 1421 | 1921 | |

- Total de tokens: **2 649 343** · Vocabulário: **32 502** termos
- Épocas cobertas: **1950 – 2026**
- Cobertura dos campos das corridas: `summary` 100%, `race` 85%, `qualifying` 42%,
  `background` 38%, `post_race` 27%
- Todos os valores estão em `data/analysis/stats.json`.

---

## 8. Problemas de qualidade encontrados

Material para a secção de *data quality* do relatório (também em `stats.json → quality`):

| Problema | Quantos | Como foi tratado |
|---|---|---|
| Links da Jolpica que levam a **páginas de desambiguação** | 28 (21 pilotos, 7 equipas) | resolvidos automaticamente (passo 3) |
| Links para **artigos que não existem** | 3 (2026 Barcelona‑Catalunya, equipas Hall e Turner) | rejeitados (`missing_article`) |
| Documentos com **pouco texto** (< 100 palavras) | 163 | rejeitados (`too_short`) |
| Várias equipas Jolpica para o **mesmo artigo** (chassis‑motor) | 40 linhas | agrupadas numa só equipa |
| Campo `status` da Jolpica **numérico e sem documentação** | — | significado deduzido da coluna `detail` (tabela abaixo) |
| Entidade HTML no nome (`Lotus-Pratt &amp; Whitney`) | 1 | descodificada |
| **Limite de pedidos** da Wikipedia (HTTP 429) | — | pedidos em lotes + respeitar `Retry-After` |
| Quantidade de texto **muito desigual por época** | — | ver `race_words_by_decade.png`: corridas dos anos 2000 têm ~4× mais texto que as dos anos 60 |

Significado deduzido do `status`:

| Código | Significado | Exemplos em `detail` |
|---|---|---|
| 0 | terminou | Finished |
| 1 | terminou com voltas de atraso | +1 Lap, +2 Laps |
| 10 | abandono por acidente | Accident, Collision, Spun off |
| 11 | abandono por avaria | Engine, Gearbox, Suspension |
| 20 | desqualificado | Disqualified, Excluded |
| 30 | não partiu | Withdrew, Did not start |

---

## 9. Decisões tomadas (e porquê)

| Decisão | Porquê |
|---|---|
| Documento = **um artigo da Wikipedia** (corrida, piloto ou equipa) | unidade natural para as necessidades de informação; liga-se facilmente aos dados estruturados |
| **Três tipos** de documento | chegar a ~2000 documentos e ter um modelo conceptual mais rico |
| Texto partido em **campos fixos** por tipo | no M2 dá para pesar campos de forma diferente no Solr (ex.: `race^3 summary^1`) |
| Mínimo de **100 palavras** | abaixo disso o artigo é só uma frase ou tabelas; com 150 perdiam-se 111 documentos a mais |
| **Wikitext** em vez de texto já extraído | a API de texto só aceita 1 artigo por pedido, e com o limite de pedidos seriam horas |
| Guardar `pageid` / `revid` e a versão do dump | a Wikipedia e a Jolpica mudam; assim sabe-se exatamente que dados foram usados |
| Pole = "partiu em 1.º na grelha" | a Jolpica não tem a pole de forma direta para todas as épocas; é uma aproximação |
| Corridas futuras de 2026 excluídas | ainda não têm resultados nem relato |
