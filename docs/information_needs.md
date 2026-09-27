# Necessidades de informação — proposta para revisão

> **Estado:** proposta para o grupo rever. Nada disto é definitivo.
> Cada necessidade tem uma descrição em inglês (pronta a copiar para o relatório),
> critérios de relevância, a query a usar no Solr (M2) e exemplos de documentos
> relevantes **confirmados à mão** na coleção.

## Como foram escolhidas

1. **Dependem do texto.** Perguntas que se respondem só com os campos estruturados
   ("quem ganhou o GP de Abu Dhabi 2021?", "pilotos portugueses") não servem para
   avaliar pesquisa em texto e foram excluídas.
2. **Cobrem os três tipos de documento**: 6 sobre corridas, 2 sobre pilotos, 2 sobre equipas.
3. **Têm variação de vocabulário.** O mesmo conceito aparece escrito de várias formas
   ("undercut", "two-stop strategy", "gambled on not needing a pit stop"), o que torna a
   pesquisa lexical (BM25) difícil e dá espaço à pesquisa semântica no M3.
4. **Têm resposta na coleção.** Para cada uma procurou-se a coleção e confirmaram-se
   exemplos relevantes.

**Sobre os "candidatos":** são o nº de documentos com uma frase que junta os termos
principais da necessidade. É uma estimativa com ruído (nem todos são relevantes e há
relevantes que não usam esses termos), útil só para saber se há material suficiente.
A relevância a sério é avaliada manualmente no M2.

## Resumo

| # | Necessidade | Tipo | Candidatos |
|---|---|---|---|
| N1 | Estratégia de pneus/boxes que decidiu a corrida | race | ~36 |
| N2 | Corridas à chuva com resultado inesperado | race | ~80 |
| N3 | Safety car que mudou o resultado ou gerou polémica | race | ~78 |
| N4 | Colisões entre colegas de equipa | race | ~95 |
| N5 | Acidentes mortais | race | ~80 |
| N6 | Desqualificações por irregularidades técnicas | race | ~64 |
| N7 | Pilotos que voltaram depois de uma lesão grave | driver | ~10 |
| N8 | Pilotos com sucesso em Le Mans ou Indianapolis | driver | ~63 |
| N9 | Equipas que fecharam por problemas financeiros | team | ~21 |
| N10 | Inovações técnicas que acabaram proibidas | team | ~11 |

---

## N1 — Estratégia que decidiu a corrida

- **Description (EN):** Races whose winner was decided by a pit-stop or tyre strategy,
  such as an undercut, a different number of stops or a gamble on not stopping.
- **Tipo:** race
- **Relevante:** o texto diz que a estratégia (nº de paragens, momento da paragem,
  escolha de pneus) foi decisiva para quem ganhou.
- **Não relevante:** a corrida só menciona paragens de rotina, ou a estratégia só
  afetou posições fora da luta pela vitória.
- **Query:** `tyre strategy pit stop decided win`
- **Vocabulário variado:** undercut, overcut, one-stop, two-stop, "gambled", "pitted early",
  "switched to a three-stop strategy".
- **Exemplos confirmados:**
  - *1958 Monaco GP*: "The team gambled on not needing a pit stop for new tyres…"
  - *2004 French GP*: "Schumacher employed a four-stop strategy to beat… Alonso"
  - *2019 Hungarian GP*: "won by Lewis Hamilton after opting for a two-stop strategy which allowed him to overtake Max Verstappen"

## N2 — Corridas à chuva com resultado inesperado

- **Description (EN):** Races affected by rain or wet conditions that produced a
  surprising result, such as a first career win, a winner from a small team or very
  few finishers.
- **Tipo:** race
- **Relevante:** a chuva/piso molhado é mencionada **e** o resultado é descrito como
  invulgar (primeira vitória, equipa pequena, poucos a terminar).
- **Não relevante:** corrida à chuva ganha pelo favorito sem nada de especial, ou
  resultado surpreendente sem relação com o tempo.
- **Query:** `rain wet race surprise first win`
- **Vocabulário variado:** rain, wet, downpour, "track dried", "wet-weather tyres";
  maiden win, "first in Formula One", "only drivers who finished".
- **Exemplos confirmados:**
  - *1975 Austrian GP*: "Mastering the wet weather, the race was won by… Vittorio Brambilla driving a March"
  - *1996 Monaco GP*: "run in wet conditions… the three podium finishers being the only drivers who finished"
  - *2008 Italian GP*: "Rain early in the race allowed Vettel to establish a solid lead" (1.ª vitória de Vettel e da Toro Rosso)
  - *2021 Hungarian GP*: "The win was Ocon's first in Formula One"

## N3 — Safety car que mudou o resultado

- **Description (EN):** Races in which a safety car period changed the outcome or
  caused controversy, for example by handing an advantage to drivers who pitted under it.
- **Tipo:** race
- **Relevante:** o safety car teve efeito claro na classificação final ou na luta pela
  vitória, ou a sua gestão foi polémica.
- **Não relevante:** o safety car só é mencionado de passagem, sem impacto no resultado.
- **Query:** `safety car changed result controversy`
- **Vocabulário variado:** safety car, virtual safety car, restart, "neutralised",
  "pitted under the safety car", "race director".
- **Exemplos confirmados:**
  - *2021 Abu Dhabi GP*: "Verstappen overtook Hamilton on the final lap after a controversial safety car restart"
  - *2008 Singapore GP*: "his teammate deliberately crashed on lap 14 to bring out the safety car"
  - *2020 Italian GP*: "Gasly… gained positions due to a well-timed pit-stop prior to a safety car"

## N4 — Colisões entre colegas de equipa

- **Description (EN):** Races in which two drivers of the same team collided with
  each other.
- **Tipo:** race
- **Relevante:** colisão (ou contacto) entre dois pilotos da mesma equipa durante a corrida.
- **Não relevante:** colisões entre pilotos de equipas diferentes; "quase colisões".
- **Query:** `teammates collided collision same team`
- **Vocabulário variado:** collided, collision, contact, "took each other out",
  "tangled", "both Mercedes drivers retired".
- **Exemplos confirmados:**
  - *1976 Brazilian GP*: "Lotus teammates Andretti and Peterson collided on the first lap"
  - *2016 Spanish GP*: "Both Mercedes drivers retired from the race following a collision with each other on the first lap"
  - *2018 Azerbaijan GP*: colisão entre Verstappen e Ricciardo (Red Bull)
- **Nota:** nem sempre o texto diz "teammate". Às vezes só dá os nomes, e a equipa vem dos
  dados estruturados. É um bom caso para combinar texto e campos (`teams`, `retirements`).

## N5 — Acidentes mortais

- **Description (EN):** Race weekends marked by the death of a driver, marshal or
  spectator.
- **Tipo:** race
- **Relevante:** morte ocorrida durante o fim de semana do Grande Prémio (treinos,
  qualificação ou corrida).
- **Não relevante:** mortes noutros eventos só referidas como contexto; acidentes graves
  sem vítimas mortais.
- **Query:** `fatal accident driver killed`
- **Vocabulário variado:** fatal, killed, died, "lost their lives", "death of", "succumbed to injuries".
- **Exemplos confirmados:**
  - *1994 San Marino GP*: "Roland Ratzenberger and… Ayrton Senna lost their lives in separate accidents"
  - *1970 Dutch GP*: "the violent fatal accident of British driver Piers Courage"
  - *1982 Belgian GP*: "overshadowed by the death of Canadian driver Gilles Villeneuve"
- **Nota:** um caso difícil é o *2014 Japanese GP*: o acidente de Bianchi foi fatal, mas
  ele morreu meses depois e o texto da corrida pode não o dizer. Serve para discutir
  os limites de uma pesquisa só por palavras.

## N6 — Desqualificações por irregularidades técnicas

- **Description (EN):** Races in which drivers were disqualified or excluded from the
  results for technical infringements, such as an underweight car, illegal fuel or
  floor wear.
- **Tipo:** race
- **Relevante:** desqualificação/exclusão (da corrida ou da qualificação) por motivo
  **técnico**.
- **Não relevante:** desqualificações por comportamento (ex.: ignorar bandeira preta,
  empurrar o carro) ou penalizações de tempo.
- **Query:** `disqualified excluded technical infringement underweight fuel`
- **Vocabulário variado:** disqualified, excluded, "did not meet the minimum weight",
  "fuel samples", "plank wear", "illegal".
- **Exemplos confirmados:**
  - *1995 Brazilian GP*: "Schumacher and Coulthard were excluded from the race result as the chemical 'fingerprint' of fuel samples…"
  - *1998 Brazilian GP*: "Damon Hill was disqualified… as his car did not meet the minimum weight requirements"
  - *2005 San Marino GP*: "his team were subsequently disqualified for underweight cars"
  - *2019 Japanese GP*: ambos os Renault desqualificados

## N7 — Pilotos que voltaram depois de uma lesão grave

- **Description (EN):** Drivers whose career was interrupted by a serious injury and
  who later returned to racing.
- **Tipo:** driver
- **Relevante:** a biografia descreve uma lesão grave **e** o regresso à competição.
- **Não relevante:** lesões sem paragem da carreira; lesões que acabaram com a
  carreira; mortes.
- **Query:** `seriously injured crash returned to racing comeback`
- **Vocabulário variado:** "seriously injured", "suffering severe burns", "broke both legs",
  "skull fracture", recovered, returned, comeback.
- **Exemplos confirmados:**
  - *Niki Lauda*: "seriously injured during the German Grand Prix… suffering severe burns"
  - *Felipe Massa*: "seriously injured during qualifying when a suspension spring…"
  - *Stirling Moss*: "Seriously injured… he missed the next three races but recovered sufficiently to win"
  - *Pedro Lamy*: "breaking both legs and wrists and sitting in the sidelines for over a year"
  - também relevantes, pelo que se sabe: Robert Kubica, Mika Häkkinen, Michael Schumacher (1999), Innes Ireland
- **Nota:** é a necessidade com menos candidatos pela pesquisa por frase (~10), mas há
  vários casos conhecidos. É um bom exemplo de como a pesquisa lexical falha
  (recall baixo).

## N8 — Pilotos com sucesso em Le Mans ou Indianapolis

- **Description (EN):** Formula One drivers who also won or competed successfully in
  the 24 Hours of Le Mans or the Indianapolis 500.
- **Tipo:** driver
- **Relevante:** a biografia refere uma vitória ou um resultado de destaque em Le Mans ou na Indy 500.
- **Não relevante:** só participação sem resultado relevante; menções a Le Mans por
  outros motivos (ex.: o acidente de 1955 como contexto).
- **Query:** `won Le Mans Indianapolis 500`
- **Vocabulário variado:** "24 Hours of Le Mans", "Le Mans 24 Hours", "Indy 500",
  "Indianapolis 500", "American open-wheel racing", "endurance racing".
- **Exemplos confirmados:**
  - *Graham Hill*: "won the Indianapolis 500 in 1966"
  - *Jim Clark*: "won the Indianapolis 500 in 1965 with Lotus"
  - *Fernando Alonso*: "a two-time winner of the 24 Hours of Le Mans with Toyota"
  - *Juan Pablo Montoya*: "a two-time winner of the Indianapolis 500"

## N9 — Equipas que fecharam por problemas financeiros

- **Description (EN):** Teams that left Formula One or collapsed because of financial
  problems, such as bankruptcy, administration or unpaid debts.
- **Tipo:** team
- **Relevante:** a história da equipa descreve uma saída ou colapso causados por
  dificuldades financeiras.
- **Não relevante:** equipas vendidas ou renomeadas sem crise financeira; problemas
  financeiros que a equipa ultrapassou.
- **Query:** `team collapsed financial difficulties administration bankrupt`
- **Vocabulário variado:** bankrupt, "entered administration", receivership, liquidated,
  debts, "unpaid bills", "collapsed financially", "withdrew due to financial difficulties".
- **Exemplos confirmados:**
  - *Super Aguri*: "withdrew from F1 after four races in the 2008 season due to financial difficulties"
  - *Brabham*: "Midway through the 1992 season, the team collapsed financially"
  - *Caterham*: "In October 2014, Caterham entered administration"
  - *Prost*: "speculation began surrounding the fate of the team in the light of its increasing debts"

## N10 — Inovações técnicas que acabaram proibidas

- **Description (EN):** Teams that introduced a technical innovation that was later
  banned by the regulations.
- **Tipo:** team
- **Relevante:** a equipa criou ou foi pioneira numa solução técnica que foi depois
  proibida.
- **Não relevante:** proibições gerais que afetaram todos por igual (ex.: o fim dos turbos
  em 1989) sem inovação da equipa; inovações que nunca foram proibidas.
- **Query:** `innovation banned fan car active suspension double diffuser`
- **Vocabulário variado:** banned, outlawed, prohibited, "declared illegal"; fan car,
  six-wheeler, ground effect, active suspension, mass damper, double diffuser, DAS.
- **Exemplos confirmados:**
  - *Brabham*: "Its unique 'fan car' won its only race, in 1978, before being withdrawn"
  - *Renault*: "the FIA banned the use of mass damper systems, developed and first used by Renault"
  - *Brawn*: "a controversial aerodynamic feature known as the double diffuser"
  - *Mercedes*: "Dual-Axis-Steering system… 2020 season"
  - *Williams*: active suspension no FW15C
- **Nota:** tem ruído. A pesquisa por "banned" apanha sobretudo a proibição dos turbos,
  que afetou todas as equipas, e isso não conta como relevante. É uma boa
  necessidade para mostrar os limites da pesquisa lexical.

---

## Próximos passos

1. **Grupo:** rever as 10, cortar ou juntar as mais fracas e afinar os critérios de relevância.
2. **Relatório M1:** usar as descrições em inglês na secção "Information needs".
3. **M2:** para cada necessidade, correr a query nos dois setups do Solr, juntar os
   top-k de ambos (pooling) e avaliar à mão cada documento como relevante ou não,
   seguindo os critérios acima. Com isso calculam-se P@k, AP/MAP e as curvas precision-recall.
