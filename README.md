# Desafio Técnico Hotmart — Analytics Engineer

Solução completa para os dois exercícios: SQL analítico e modelagem/ETL
histórico para GMV diário por subsidiária.

# Desafio Técnico Hotmart — Analytics Engineer
 
Solução completa para os dois exercícios: SQL analítico e modelagem/ETL
histórico para GMV diário por subsidiária.
 
---
 
## Estrutura dos entregáveis










---
 
## Regra de GMV — consolidada do PDF + vídeo + diagrama
 
Uma compra compõe o GMV se e somente se **ambas** as condições forem verdadeiras:
 
1. `release_date IS NOT NULL` — pagamento foi efetuado (vídeo da Catarina)
2. `purchase_status = 'APROVADA'` — não foi cancelada nem reembolsada
   (do diagrama: status possíveis = INICIADA, APROVADA, CANCELADA, REEMBOLSADA;
    e do PDF: *"pagamento foi efetuado e não foi cancelado"*)
Esta regra é **materializada na coluna `is_gmv_eligible`** da tabela final —
o usuário de negócio não precisa conhecer a regra composta, basta filtrar
`WHERE is_gmv_eligible = TRUE`. Isto atende diretamente ao requisito *"a
modelagem precisa ajudar pessoas que não possuem conhecimentos sólidos em SQL"*.
 
---
 
## Exercício 1 — SQL
 
### Decisões-chave
 
**Filtros aplicados em ambas as queries:**
- `release_date IS NOT NULL`
- `purchase_status = 'APROVADA'`
  
**Pergunta 1 — filtro temporal por `release_date`:** o faturamento é
reconhecido no dia em que o pagamento foi efetuado, não no dia do pedido.
Uma compra pedida em dez/2020 e paga em jan/2021 compõe o faturamento de
1.    Se o time de negócios preferir `order_date`, troca-se a coluna do
filtro — a arquitetura da query é a mesma.
 
**Pergunta 2 — `ROW_NUMBER` vs `RANK`:** usei `ROW_NUMBER` para garantir
exatamente 2 produtos por produtor mesmo com empate. Troca-se para `RANK`
se o negócio preferir "trazer todos os empatados".
 
>**Join otimizado pelo particionamento:** `ON pi.prod_item_id =
>p.prod_item_id AND pi.prod_item_partition = p.prod_item_partition`. O
>segundo predicado permite ao engine fazer partition pruning no lado
>`product_item`, reduzindo significativamente o volume escaneado.
 
---

## Exercício 2 — Modelagem e ETL
 
### A tabela final: `analytics.fct_purchase_history`
 
**Grão:** 1 linha por `(purchase_id, transaction_date)` — um snapshot por
dia em que a compra sofreu qualquer alteração em qualquer das 3 fontes.
 
**Colunas principais:**
- Identidade e tempo: `purchase_id`, `transaction_date` (partição)
- De `purchase`: `buyer_id`, `prod_item_id`, `order_date`, `release_date`,
  `producer_id`, `purchase_total_value`, **`purchase_status`**
- Partições do lake: `purchase_partition`, `prod_item_partition` (lineage/otimização)
- De `product_item`: `product_id`, `item_quantity`, `purchase_value`
- De `purchase_extra_info`: `subsidiary`
- Metadados: `is_current`, **`is_gmv_eligible`**, `updated_sources`, `etl_loaded_at`
### Por que esse grão?
- Consulta por estado corrente é trivial: `WHERE is_current = TRUE`.
- Navegação no tempo é trivial: `WHERE transaction_date <= :cutoff`.
- Auditoria é trivial: `SELECT * WHERE purchase_id = X ORDER BY transaction_date`.
- Particionamento por `transaction_date` casa com pipeline D-1: cada run
  só toca a partição do dia.
### O algoritmo (5 passos)
 
1. **Deduplicação intradiária.** Cada fonte é CDC, pode ter múltiplos
   eventos no mesmo dia para a mesma compra. Pegamos o último
   (`ROW_NUMBER() OVER (PARTITION BY purchase_id, transaction_date ORDER BY transaction_datetime DESC) = 1`).
2. **Esqueleto.** UNION dos `(purchase_id, transaction_date)` das 3
   fontes. Guardo flags `has_*` para registrar quais fontes dispararam
   a linha.
3. **Join.** LEFT JOIN do esqueleto com cada fonte. Dias em que uma
   fonte não atualizou ficam NULL nos campos daquela fonte.
4. **Forward fill.** `LAST_VALUE(col IGNORE NULLS) OVER (PARTITION BY
   purchase_id ORDER BY transaction_date ROWS UNBOUNDED PRECEDING)`.
   Propaga o último valor não-nulo conhecido de cada campo para os
   dias seguintes da mesma compra. Nota importante: `purchase_status`
   também é forward-filled — se uma compra for cancelada retroativamente,
   o status 'CANCELADA' propaga e `is_gmv_eligible` passa a FALSE a
   partir daquele `transaction_date`.
5. **Metadados.** `is_current`, `is_gmv_eligible` (regra de negócio),
   `updated_sources` (array das fontes), `etl_loaded_at`.
### Requisitos do enunciado — como cada um é atendido
 
| Requisito | Como é atendido |
|---|---|
| Histórico e imutável | Cada evento vira uma linha; nunca se atualiza linha existente. Reprocessamento full produz o mesmo resultado (eventos são imutáveis). |
| Passado não muda no reprocess | Idempotência por construção: o ETL é uma função pura dos eventos. |
| Rastreabilidade diária | Grão diário + coluna `updated_sources`. |
| Navegação no tempo | `WHERE transaction_date <= :cutoff` + último snapshot por purchase_id. |
| D-1 | O pipeline roda com `transaction_date = CURRENT_DATE - 1`. |
| Partição por `transaction_date` | `PARTITION BY transaction_date` no DDL. |
| Estado corrente fácil | `WHERE is_current = TRUE`. |
| Se fonte A atualizou e B/C não, repete valores ativos | Passo 4 (forward fill). |
| Ajuda quem não sabe SQL avançado | Tabela wide (todos os campos resolvidos) + `is_gmv_eligible` materializada — usuário só faz `SUM` + `GROUP BY`. |
| GMV exclui canceladas/reembolsadas | `purchase_status = 'APROVADA'` em `is_gmv_eligible`. |
 
### Sobre a "navegação no tempo" — nuance importante
 
O PDF diz: *"os valores retornados pela consulta não podem ser diferentes"*.
 
Isto **não** significa que "GMV de Jan/23 visto em 31/03" = "GMV de Jan/23
visto hoje". O vídeo da Catarina é claro: se uma compra foi alterada em
fev/23, o GMV retrospectivo de janeiro muda.
 
O que o requisito significa é: **uma consulta com um cutoff específico é
100% reprodutível**. A consulta "GMV de Jan/23 com cutoff em 31/03/2023"
retorna o mesmo valor hoje ou daqui a 5 anos — porque a tabela é imutável
e o cutoff está explícito.
 
### Validação com os dados do PDF
 
`simulacao_etl.py` roda a lógica completa sobre os dados exatos do
enunciado (com `purchase_status` e `purchase_total_value` inferidos).
Resultados reais da execução:
 
**Dataset final populado** — 10 linhas:
- Compra 55: 5 snapshots (20/01, 23/01, 05/02, 12/07, 15/07)
- Compra 56: 2 snapshots (25/01, 26/01)
- Compra 69: 3 snapshots (26/02, 28/02, 12/03)
 
**GMV corrente por subsidiária (executado):**

| data_compra | subsidiaria | gmv |
|---|---|---|
| 2023-01-20 | nacional | 55.00 |
| 2023-02-26 | internacional | 2000.00 |
 
**Compra 56 não aparece** — `is_gmv_eligible = FALSE` porque
`purchase_status = 'INICIADA'` e `release_date IS NULL`.
 
**Compra 69** aparece como internacional (última atualização da
subsidiária em 12/03 sobrescreveu "nacional" de 28/02).
 
**Navegação no tempo — compra 55 (executado):**
- GMV Jan/23 com cutoff em 31/03/2023 → R$ 50,00
- GMV Jan/23 sem cutoff (hoje) → R$ 55,00
Cada uma das duas consultas, **com seus cutoffs fixos**, é 100%
reprodutível.
 
---
 
## Tech stack sugerida
 
| Camada | Escolha | Por quê |
|---|---|---|
| Armazenamento | **Delta Lake** (S3/GCS/ADLS) em formato Parquet particionado | ACID transactions + time travel nativo, reforça a propriedade de imutabilidade. |
| Processamento | **PySpark** no Databricks/EMR/Dataproc | Escala horizontal; window functions nativas; suporte a `LAST_VALUE IGNORE NULLS`. |
| Orquestração | **Airflow** ou **Dagster** | DAG com dependências das 3 fontes raw → fct_purchase_history → consumidores. |
| Transformação declarativa (alternativa) | **dbt** sobre BigQuery/Snowflake | O script PySpark é uma sequência de SQLs — traduz 1:1 para modelos dbt; cada passo vira um CTE/modelo separado com testes. |
| Data quality | **Great Expectations** ou testes dbt | Testes: unicidade de `(purchase_id, transaction_date)`; `is_current` exatamente 1 por `purchase_id`; `purchase_value >= 0`; `purchase_status IN ('INICIADA','APROVADA','CANCELADA','REEMBOLSADA')`; `subsidiary IN ('nacional','internacional')`. |
| BI / consumo | Metabase / Looker / Hex | Exposição de `fct_purchase_history` como fonte única de verdade; `is_gmv_eligible` já embute a regra. |
 
### Qualidade de dados — casos tratados
 
- Eventos duplicados no mesmo dia → resolvido no Passo 1 (último evento vence).
- `release_date IS NULL` (compra não paga) → excluída do GMV via
  `is_gmv_eligible`, mas **mantida no histórico** (aparece até ser paga
  ou cancelada).
- `purchase_status = 'CANCELADA'` ou `'REEMBOLSADA'` → excluída do GMV
  via `is_gmv_eligible`, mas mantida no histórico para auditoria.
- Primeira linha de uma compra onde uma fonte não chegou ainda
  (ex.: compra 56 no dia 25/01 com campos de `purchase` NULL) →
  mantida no histórico; o forward fill preenche quando a fonte chega.
- Reenvio de eventos (correção retroativa) → absorvido automaticamente
  no próximo run do ETL; gera novo snapshot com novo `transaction_date`.
### Evolução para produção (incremental)
 
O script atual faz full refresh para simplicidade. Em produção:
1. Ler apenas `transaction_date = CURRENT_DATE - 1` de cada fonte.
2. Identificar `purchase_id`s afetados.
3. Reprocessar o forward fill desses `purchase_id`s (desde a primeira
   aparição ou desde o último snapshot consolidado).
4. MERGE na partição `CURRENT_DATE - 1` da tabela final.
5. Recalcular `is_current` para os `purchase_id`s afetados (vira FALSE na
   linha anteriormente current, TRUE na nova linha inserida).