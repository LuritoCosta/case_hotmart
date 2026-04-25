# Case Hotmart — Analytics Engineer
 
Solução para o desafio técnico da vaga de Analytics Engineer da Hotmart.
Composta por dois exercícios: SQL analítico sobre tabelas correntes e
modelagem/ETL histórico para GMV diário por subsidiária.

---
 
## 📁 Estrutura
 
```
case_hotmart/
├── app/
│   └── app.py                          # Orquestrador (roda os 2 scripts)
├── data/
│   ├── raw/                            # CSVs de entrada
│   │   ├── purchase_current.csv        # tabela corrente (Exercício 1)
│   │   ├── product_item_current.csv    # tabela corrente (Exercício 1)
│   │   ├── purchase_events.csv         # eventos CDC (Exercício 2)
│   │   ├── product_item_events.csv     # eventos CDC (Exercício 2)
│   │   └── extra_info_events.csv       # eventos CDC (Exercício 2)
│   └── specialized/
│       └── fct_purchase_history.csv    # output do ETL
├── sql/
│   ├── exercicio1_pergunta1.sql        # Top 50 produtores em 2021
│   ├── exercicio1_pergunta2.sql        # Top 2 produtos por produtor
│   ├── exercicio2_ddl_tabela_final.sql # DDL fct_purchase_history
│   └── exercicio2_consulta_final.sql   # GMV diário + navegação no tempo + auditoria
├── src/
│   ├── 01_gerar_bases.py               # Gera CSVs raw a partir do PDF
│   ├── 02_testes_sql.py                # Executa SQL via DuckDB para validar
│   └── 03_simulacao_etl.py             # ETL em pandas (5 passos)
├── Desafio Técnico - AE.pdf
├── .gitignore
├── requirements.txt
└── README.md
```

---
## 🚀 Como rodar
 
```bash
# 1. Instalar dependências
pip install -r requirements.txt
 
# 2. Rodar tudo de uma vez
python app/app.py
 
# Variações úteis:
python app/app.py --skip-etl         # pular ETL
 
# Ou rodar cada step manualmente
cd src/
python 01_gerar_bases.py
python 03_simulacao_etl.py
```
 
---

## 📘 Exercício 1 — SQL
 
### Decisões aplicadas em ambas as queries
 
**Filtros de negócio** (vídeo da Catarina + diagrama):
- `release_date IS NOT NULL` — só faturamos se a compra foi paga
- `purchase_status = 'APROVADA'` — exclui INICIADA, CANCELADA, REEMBOLSADA

**Cálculo do faturamento:**
```sql
SUM(purchase_value)
```
Cada linha da tabela `purchase` representa uma ocorrência completa de venda.
O `purchase_value` em `product_item` traz o valor da compra associada,
então o faturamento é a soma simples desse valor para as compras que
atendem aos filtros de negócio. O campo `item_quantity` é informação
agregadora da compra que não é considerada no cálculo de faturamento
neste exercício.
 
**Join otimizado:** `prod_item_id + prod_item_partition` para permitir partition
pruning quando estas tabelas estiverem em um data lake particionado.
 
### Pergunta 1 — Top 50 produtores em 2021
 
Filtro temporal por `release_date` (faturamento é reconhecido no dia do
pagamento, não do pedido). Uma compra pedida em dez/2020 e paga em jan/2021
entra no faturamento de 2021.
 
### Pergunta 2 — Top 2 produtos por produtor
 
CTE com agregação por `(producer_id, product_id)`, depois `ROW_NUMBER()`
particionado por produtor. Sem recorte temporal (a pergunta não especifica).
 
`ROW_NUMBER` foi escolhido sobre `RANK` para garantir exatamente 2 produtos
por produtor mesmo com empate. Tiebreaker em `product_id ASC` para
reprodutibilidade.
 
---
 
## 📗 Exercício 2 — Modelagem e ETL
 
### Tabela: `analytics.fct_purchase_history`
 
**Grão:** 1 linha por `(purchase_id, transaction_date)` — um snapshot por
dia em que a compra sofreu qualquer alteração em qualquer das 3 fontes.
 
**Partição:** `transaction_date` (D-1 via pipeline diário).
 
### Algoritmo (5 passos no ETL)
 
1. **Deduplicação intradiária** — último evento do dia por fonte
   (`drop_duplicates(keep='last')` ordenado por `transaction_datetime`).
2. **Esqueleto** — UNION dos `(purchase_id, transaction_date)` das 3 fontes
   com flags `has_purchase`, `has_product_item`, `has_extra_info`.
3. **Join** — left merge do esqueleto com as 3 fontes deduplicadas.
4. **Forward fill** — `groupby('purchase_id').ffill()` ordenado por
   `transaction_date` propaga os últimos valores conhecidos por compra.
   Inclui `purchase_status` — cancelamentos retroativos viram
   `is_gmv_eligible=FALSE` a partir do dia do evento.
5. **Metadados** — `is_current`, `is_gmv_eligible`, `updated_sources`,
   `etl_loaded_at`.
### Regra de GMV — encapsulada na coluna `is_gmv_eligible`
 
```python
is_gmv_eligible = (release_date IS NOT NULL) AND (purchase_status == 'APROVADA')
```
 
**Por que essa coluna existe?** O enunciado pede explicitamente *"a
modelagem precisa ajudar pessoas que não possuem conhecimentos sólidos em
SQL"*. Em vez do usuário lembrar de uma regra composta, basta filtrar a
flag. Se a regra mudar (ex.: incluir `'ESTORNADA'`), muda em um único
lugar (o ETL) e todas as consultas downstream continuam corretas.
 
### Como cada requisito é atendido
 
| Requisito | Implementação |
|---|---|
| Histórico e imutável | Cada evento gera nova linha; nunca se edita linha existente |
| Passado não muda no reprocess | Eventos imutáveis + ETL como função pura → idempotente |
| Rastreabilidade diária | Grão `(purchase_id, transaction_date)` + `updated_sources` |
| Navegação no tempo | `WHERE transaction_date <= :cutoff` + último snapshot |
| D-1 | Pipeline lê `transaction_date = CURRENT_DATE - 1` em produção |
| Partição por `transaction_date` | Coluna física + key de partição |
| Estado corrente fácil | `WHERE is_current = TRUE` |
| Fonte A atualizou e B/C não, repete valor ativo | Forward fill (Passo 4) |
| Ajudar usuário sem SQL avançado | Tabela wide + `is_gmv_eligible` pré-calculada |
| GMV exclui canceladas/reembolsadas | `purchase_status = 'APROVADA'` em `is_gmv_eligible` |
 
### Sobre as "lacunas" iniciais — decisão de design
 
A tabela final tem alguns NULLs nas primeiras linhas de algumas compras.
Isso é **comportamento intencional**, não bug.
 
Exemplo da compra 56:
- 25/01/2023: chegaram `product_item` e `extra_info`, mas `purchase` ainda não → campos de purchase ficam NULL
- 26/01/2023: `purchase` chega → linha completa
Forward fill **não pode** preencher os NULLs do dia 25 porque não havia
"valor anterior" — a compra simplesmente ainda não tinha sido vista pelo
data lake. Backward fill seria possível, mas violaria a imutabilidade do
passado: estaríamos inventando que sabíamos algo no dia 25 que só ficamos
sabendo no dia 26.
 
**Estratégia adotada: forward fill apenas.** A regra do enunciado fala em
*"dados ATIVOS das demais"* — se não há dado ativo, não há o que repetir.
O NULL inicial é registro honesto do que o data lake conhecia naquele
momento.
 
### Sobre "navegação no tempo" — nuance importante
 
O PDF diz: *"os valores retornados pela consulta não podem ser diferentes"*.
 
Isso **não** significa que "GMV de Jan/23 visto em 31/03" = "GMV de Jan/23
visto hoje". O vídeo da Catarina é claro: se uma compra foi alterada em
fev/23, o GMV retrospectivo muda.
 
O requisito significa: **uma consulta com cutoff específico é 100%
reprodutível**. "GMV de Jan/23 com cutoff em 31/03/2023" retorna o mesmo
valor hoje ou daqui a 5 anos.
 
Validação executada no `03_simulacao_etl.py` (compra 55):
- Com cutoff 31/03/2023 → `purchase_value = 50.00`
- Sem cutoff (estado corrente) → `purchase_value = 55.00`
Cada consulta isolada é determinística. ✓
 
---

## 🛠 Stack
 
- **Python 3.10+**
- **pandas** — ETL (5 passos sobre DataFrames)
- **DuckDB** — execução do SQL ANSI puro sobre arquivos CSV (Exercício 1)

Em produção, a stack seria evoluída para um data lake distribuído (S3 +
Spark/Glue + Athena, ou equivalente em GCP/Azure). O algoritmo
do ETL é o mesmo — apenas a engine muda. As 5 etapas são todas window
functions e joins padrão SQL/Spark.
 
---