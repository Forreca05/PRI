# Solr — guia rápido

Como pôr o motor de pesquisa a funcionar com a coleção F1 e como avaliar os resultados.
Baseado no tutorial *05-solr* da cadeira, adaptado ao nosso projeto.

---

## Índice

1. [Arranque rápido](#1-arranque-rápido)
2. [O que está nesta pasta](#2-o-que-está-nesta-pasta)
3. [Onde entra o Solr](#3-onde-entra-o-solr)
4. [Correr o Solr (Docker)](#4-correr-o-solr-docker)
5. [Indexar os documentos](#5-indexar-os-documentos)
6. [Schema e analyzers](#6-schema-e-analyzers)
7. [Fazer pesquisas](#7-fazer-pesquisas)
8. [Avaliar o sistema](#8-avaliar-o-sistema)
9. [Ciclo de trabalho](#9-ciclo-de-trabalho)
10. [Problemas comuns](#10-problemas-comuns)

---

## 1. Arranque rápido

Requisitos: Docker e a coleção já gerada (`cd pipeline && make` cria `data/processed/documents.json`).

```bash
./solr/startup.sh                    # Solr + schema + 2058 documentos (+ core sem schema)
.venv/bin/python solr/search.py      # corre as queries N1–N13 nos sistemas
# preencher a coluna 'relevant' em solr/qrels/*.csv com 1 ou 0
.venv/bin/python solr/evaluate.py    # P@10, AP, MAP e curva precision-recall
```

Interface do Solr: http://localhost:8983 → *Core Selector* `f1`.

### Voltar a ligar a app de pesquisa

A partir da pasta `Projeto`, com o Docker ligado:

```bash
docker start meic_solr               # liga o Solr (mantém os dados já indexados)
.venv/bin/python solr/webapp.py      # liga a app; deixar este terminal aberto
```

Abrir http://localhost:8000. Para desligar: `Ctrl+C` no terminal da app e `docker stop meic_solr`.

- Se o `docker start` disser que o `meic_solr` não existe, correr `./solr/startup.sh` em vez dele.
- Se a app der `Address already in use`, já está ligada: basta abrir o link.
- Depois de mudar o `queries.json`, reiniciar a app, porque ela só o lê ao arrancar.

---

## 2. O que está nesta pasta

| Ficheiro | Pergunta a que responde |
|---|---|
| `startup.sh` | Como ponho o Solr a funcionar com os nossos dados? |
| `schema.json` | Como é que o Solr analisa o texto de cada campo? |
| `queries.json` | O que pesquiso para cada necessidade, e com que configuração (sistema)? |
| `search.py` | O que é que o Solr devolve para cada query? |
| `qrels/N*.csv` | Desses resultados, quais são realmente relevantes? (**preenchido à mão**) |
| `evaluate.py` | Quão bom é cada sistema? |
| `results/` | Gerado: rankings, `metrics.csv` e `precision_recall.png` |

---

## 3. Onde entra o Solr

O Solr **é o motor de pesquisa**: guarda os documentos, analisa o texto, encontra os
documentos que respondem a uma query e ordena-os por *score* (BM25). Os scripts Python
só lhe fazem perguntas e guardam as respostas.

```
documents.json ──(startup.sh)──▶ SOLR  guarda e indexa os 2058 documentos
                                   ▲  │
                     pergunta (HTTP)  │  resposta: top 10 ordenado por score
                                   │  ▼
queries.json ──▶ search.py ──▶ results/*.json + qrels/*.csv
                                              │
                    avaliação manual 1/0 ─────┘
                                              ▼
                                        evaluate.py ──▶ P@10, AP, MAP
```

O que se avalia é **a qualidade das respostas do Solr**. Mudar o schema ou os parâmetros
da query muda o comportamento do Solr, e as métricas mostram se melhorou ou piorou.

---

## 4. Correr o Solr (Docker)

O `startup.sh` faz isto automaticamente, mas o comando por trás é:

```bash
docker run -p 8983:8983 --name meic_solr -v ${PWD}:/data -d solr:10 solr-precreate f1
```

| Opção | Significado |
|---|---|
| `-p 8983:8983` | liga a porta do Solr ao nosso computador (para abrir http://localhost:8983) |
| `--name meic_solr` | nome do container, para o referir depois |
| `-v ${PWD}:/data` | a pasta atual fica visível dentro do container em `/data` |
| `-d` | corre em segundo plano |
| `solr:10` | versão do Solr (fixa — não mudar a meio do projeto) |
| `solr-precreate f1` | cria uma coleção (core) vazia chamada `f1` |

Comandos úteis:

```bash
docker ps                  # que containers estão a correr
docker logs -f meic_solr   # ver o que o Solr está a fazer (Ctrl+C para sair)
docker stop meic_solr      # desligar
docker start meic_solr     # voltar a ligar (os dados mantêm-se)
docker rm -f meic_solr     # apagar (perde-se tudo → correr startup.sh outra vez)
```

> `docker run` **cria** um container novo; para religar um que já existe usa-se `docker start`.

---

## 5. Indexar os documentos

**Coleção (core):** é onde ficam os documentos. No tutorial chama-se `courses`; aqui é `f1`.
Para nós, *core* e *coleção* são a mesma coisa.

**Indexar** é enviar os documentos para o Solr. Há duas formas equivalentes:

```bash
# via HTTP (a que o startup.sh usa)
curl -X POST -H 'Content-Type: application/json' \
    --data-binary @../data/processed/documents.json \
    'http://localhost:8983/solr/f1/update?commit=true'

# via CLI dentro do container (o ficheiro tem de estar acessível em /data)
docker exec meic_solr solr post -c f1 /data/documents.json
```

Cada documento tem de ter um `id` único. Os nossos já têm (`race_1996_06`,
`driver_senna`, …), por isso reenviar **substitui** em vez de duplicar.

---

## 6. Schema e analyzers

### Porque é preciso um schema

Sem schema, o Solr fica em modo *schemaless*: adivinha o tipo de cada campo e engana-se
(transforma tudo em listas, não ignora acentos, …). O exemplo do tutorial: pesquisar
"computaçao" sem acento não encontra "Computação". No nosso caso o equivalente seria
"raikkonen" não encontrar "Räikkönen".

### Como funciona

O **schema** (`schema.json`) diz o tipo de cada campo. Os campos de texto têm um
**analyzer**, uma cadeia de processamento:

- **tokenizer** — parte o texto em palavras;
- **filters** — transformam as palavras, um a seguir ao outro (como *pipes* em Unix).

O analyzer corre **duas vezes**: ao indexar (no texto dos documentos) e ao pesquisar (na
query). Assim os dois lados ficam no mesmo formato e fazem *match*. O valor original
continua guardado tal como está — o analyzer só afeta o que é usado para pesquisar.

### Os nossos tipos

| Tipo | Filtros | Campos | Exemplo |
|---|---|---|---|
| `f1_text` | possessivos (`Senna's`→`Senna`), sem acentos, minúsculas, sem stopwords de inglês, stemming (Porter) | `summary`, `background`, `qualifying`, `race`, `post_race`, `other`, `biography`, `history`, `layout`, `events` | "crashing" encontra "crashed" |
| `f1_name` | sem acentos, minúsculas (**sem** stemming, para não estragar nomes) | `title`, `winner`, `podium`, `drivers`, `teams`, `circuit`, … | "raikkonen" encontra "Räikkönen" |
| `string` | nenhum — valor exato | `type`, `country`, `nationality`, ids | `fq=type:race` |
| `pint` / `plong` / `pdouble` | — | `season`, `wins`, `starters`, `latitude`, … | `season:[1980 TO 1989]` |
| `f1_date` (`DateRangeField`) | — | `date`, `date_of_birth` | `date:[1990-01-01 TO 1990-04-30]` |

`DateRangeField` foi escolhido porque aceita datas no formato `1950-05-13` tal como vêm
dos dados (o tipo de data normal exige `1950-05-13T00:00:00Z`).

### Ordem importante

O schema tem de ser enviado **antes** dos documentos, porque não se aplica a documentos já
indexados. Por isso o `startup.sh` faz sempre: container novo → schema → documentos.
**Sempre que se muda o `schema.json`, corre-se o `startup.sh` outra vez.**

O `startup.sh` cria também um segundo core, `f1_schemaless`, com o configset por omissão do
Solr e **sem** o nosso `schema.json`: o Solr adivinha o tipo de cada campo pelo primeiro valor
(texto → `text_general`, sem stemming nem stopwords, e sem `all_text`). Serve de baseline
"sem schema" na avaliação (sistema `schemaless` do `queries.json`, campo `"core"`).

Ver a definição atual de um campo ou tipo:

```bash
curl http://localhost:8983/solr/f1/schema/fields/title
curl http://localhost:8983/solr/f1/schema/fieldtypes/f1_text
```

---

## 7. Fazer pesquisas

### Na interface

http://localhost:8983 → *Core Selector* `f1` → **Query** → preencher → **Execute Query**.
Por cima dos resultados aparece o URL equivalente (dá para copiar).

| Parâmetro | O que faz | Exemplo |
|---|---|---|
| `q` | a pesquisa | `rain wet surprise` |
| `fq` | filtra **sem** mexer no score | `type:race`, `season:[1980 TO 1989]` |
| `fl` | campos a devolver (`score` incluído) | `id,title,score` |
| `sort` | ordenar por outra coisa que não o score | `date asc` |
| `rows` | quantos resultados | `10` |
| `defType` | o parser da query | `edismax` |
| `qf` | (eDisMax) campos onde procurar e peso de cada | `summary^3 race^2 title` |
| `pf` | (eDisMax) bónus quando as palavras aparecem juntas como frase | `race^3` |
| `debugQuery` | explica como foi calculado o score de cada documento | ✓ |

Outras abas úteis:
- **Analysis** — escreve-se uma palavra (ex.: "Räikkönen", "crashing") e vê-se em que
  tokens o schema a transforma.
- **Schema** — ver campos e tipos.

### Parsers

- **Lucene (o normal):** tudo à mão — `summary:rain OR race:rain OR title:rain`.
- **eDisMax:** escrevem-se só as palavras; o `qf` diz em que campos procurar e com que peso.
  É o que usamos no `queries.json`.

### Sintaxe de query

| Funcionalidade | Exemplo | Significado |
|---|---|---|
| Wildcard | `title:mon*` | começa por "mon" |
| Fuzzy | `title:hamilten~1` | aceita 1 letra de diferença |
| Proximidade | `race:"safety car lead"~5` | palavras a até 5 posições umas das outras |
| Frase | `"pit stop"` | palavras seguidas |
| Intervalo | `season:[1980 TO 1989]`, `wins:[10 TO *]` | valores entre limites |
| Boost | `rain^3 wet` | "rain" pesa 3× mais |
| Operadores | `rain AND NOT monaco` | combinar termos |

Documentação completa: https://solr.apache.org/guide/solr/10_0/

### Pela linha de comandos

É isto que o `search.py` faz por baixo para cada query:

```bash
curl -G http://localhost:8983/solr/f1/select \
  --data-urlencode 'q=rain wet surprise shock unexpected "first win" "only three"' \
  --data-urlencode 'defType=edismax' \
  --data-urlencode 'qf=title^2 summary^3 race^2' \
  --data-urlencode 'fq=type:race' \
  --data-urlencode 'fl=id,title,score'
```

```json
"numFound": 403,
"docs": [
  {"id": "race_1967_02", "title": "1967 Monaco Grand Prix", "score": 13.97},
  {"id": "race_2019_11", "title": "2019 German Grand Prix", "score": 13.69},
  {"id": "race_1984_06", "title": "1984 Monaco Grand Prix", "score": 13.11}
]
```

---

## 8. Avaliar o sistema

Testar um sistema de pesquisa é medir **quantos dos resultados devolvidos são relevantes**
para cada necessidade de informação (N1–N13, tabela do relatório).

### `queries.json`

Tem duas partes:

- **`systems`** — configurações do Solr a comparar. Neste momento:
  - `simple` (baseline): eDisMax num único campo, `all_text` (cópia de todos os campos de
    texto), sem pesos e sem filtro por tipo de documento (`"filter_type": false`);
  - `boosted`: pesos por campo (`qf`), bónus para pares de palavras próximas (`pf2`, `ps2`) e filtro por tipo.
- **`needs`** — as 13 necessidades, cada uma com o tipo de documento (que vira
  `fq=type:...`) e a query `q`.

Para testar outra ideia basta acrescentar um sistema novo em `systems`.

### `search.py` — faz as pesquisas

1. Para cada sistema e cada necessidade, envia a query ao Solr (como carregar em
   *Execute Query*, mas feito pelo código).
2. Guarda o top 10 em `results/<sistema>.json`:
   ```json
   "N2": ["race_1967_02", "race_2019_11", "race_1984_06", ...]
   ```
3. Cria/atualiza `qrels/N1.csv` … `N13.csv` com **todos** os documentos devolvidos por
   qualquer sistema (cada um só aparece uma vez), com um excerto onde as palavras da query
   aparecem entre `[ ]`.

Ao correr outra vez, **as avaliações já feitas mantêm-se**; só são acrescentados
documentos novos com `relevant` vazio.

### Avaliação manual (qrels)

Abrir cada `qrels/N*.csv` e preencher a coluna `relevant` com **1** (relevante) ou **0**,
segundo o critério definido no relatório para essa necessidade:

```
id,title,relevant,snippet
race_2002_10,2002 British Grand Prix,0,"...cloudy and [wet] weather..."
race_1996_06,1996 Monaco Grand Prix,1,"..."
```

Exemplo do critério de N2: só é relevante se choveu **e** o resultado foi surpreendente.
Uma corrida à chuva ganha pelo favorito não conta.

Se o excerto não chegar para decidir, ver o documento completo na interface
(`q=id:race_1996_06`, `fl=*`) ou na Wikipedia.

> As avaliações de relevância têm de ser feitas por nós, não por IA.

### `evaluate.py` — calcula as métricas

Não fala com o Solr: compara a ordem que o Solr devolveu com as avaliações dos `qrels`.

| Métrica | Significado |
|---|---|
| **P@10** | dos 10 primeiros, quantos são relevantes (6 relevantes → 0.6) |
| **AP** | como o P@10, mas premeia ter os relevantes **mais acima** na lista |
| **MAP** | média das AP das 13 necessidades — um número por sistema, para os comparar |
| **Curva P-R** | precisão interpolada em 11 níveis de recall, uma linha por sistema |

Os documentos relevantes são os marcados com 1 entre tudo o que algum sistema devolveu
(*pooling*), por isso o recall é relativo a esse conjunto. Documentos por avaliar contam
como não relevantes e o script avisa.

Saídas (valores ilustrativos):

```
need   simple P@10   simple AP   boosted P@10   boosted AP
N1            0.40       0.312           0.60        0.541
...
MAP                      0.287                       0.455
```

- `results/metrics.csv` — a tabela acima;
- `results/precision_recall.png` — o gráfico.

---

## 9. Ciclo de trabalho

1. **Explorar na interface** do Solr até a query de uma necessidade parecer boa.
2. **Passar** os parâmetros para o `queries.json` (query em `needs`, `qf`/`pf` em `systems`).
3. Correr `search.py` → avaliar os documentos novos nos `qrels/` → correr `evaluate.py`.
4. Para mudar **como o texto é analisado**: editar `schema.json` → `startup.sh` → passo 3.
5. Comparar a MAP e as curvas entre sistemas.

Exemplo de um caso já encontrado: em N2, a palavra "shock" (de "resultado surpreendente")
traz o *1951 Indianapolis 500* por causa de "shock absorber" (amortecedor) — um caso
típico dos limites de uma pesquisa baseada só em palavras.

---

## 10. Problemas comuns

| Erro | Causa | Solução |
|---|---|---|
| `The container name "/meic_solr" is already in use` | o container já existe | `docker start meic_solr`, ou `docker rm -f meic_solr` e criar de novo (ou só `./solr/startup.sh`) |
| `cannot remove container ... container is running` | está ligado | `docker rm -f meic_solr` |
| `Connection refused` no `search.py` | Solr desligado ou ainda a arrancar | `docker start meic_solr` e esperar uns segundos |
| Mudei o schema e nada mudou | o schema não se aplica a documentos já indexados | `./solr/startup.sh` |
| `Warning: unjudged documents` no `evaluate.py` | há linhas com `relevant` vazio nos `qrels` | preencher com 1 ou 0 |
