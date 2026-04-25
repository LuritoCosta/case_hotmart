"""
=============================================================================
DESAFIO TÉCNICO HOTMART - ANALYTICS ENGINEER
Script: 04_simulacao_etl.py
=============================================================================
ETL em pandas que constrói a tabela histórica fct_purchase_history
a partir das 3 tabelas de eventos.

Mantém a estrutura de 5 passos:
    1. Deduplicação intradiária (último evento do dia por fonte)
    2. Esqueleto (união dos pares purchase_id × transaction_date)
    3. Join do esqueleto com as 3 fontes
    4. Forward fill por purchase_id ordenado por transaction_date
    5. is_current + is_gmv_eligible + updated_sources + etl_loaded_at

ESTRATÉGIA DE LACUNAS (decisão de design):
    Apenas FORWARD FILL.
    Quando uma compra aparece no esqueleto em um dia em que uma das fontes
    AINDA não existia (ex.: compra 56 no dia 25/01: product_item e
    extra_info chegaram, mas purchase só veio em 26/01), os campos da
    fonte ausente ficam como NULL — não há "valor anterior" para copiar.

    Esta é a leitura honesta do enunciado: "se uma tabela sofreu
    atualização e as demais não, os DADOS ATIVOS das demais deverão ser
    repetidos". Se ainda não há dado ativo, não há o que repetir. O NULL
    inicial é informação legítima — registra que naquele momento o data
    lake ainda não tinha visto aquela informação.

    Quando a fonte que faltava chega, forward fill preenche os dias
    seguintes normalmente.

REGRA DE GMV (PDF + vídeo + diagrama):
    is_gmv_eligible = (release_date IS NOT NULL) AND (purchase_status = 'APROVADA')

=============================================================================
"""

import os
import pandas as pd
from datetime import datetime

BASE = os.path.join(os.path.dirname(__file__), '..')
RAW  = os.path.join(BASE, 'data', 'raw')
SPEC = os.path.join(BASE, 'data', 'specialized')
os.makedirs(SPEC, exist_ok=True)


# =============================================================================
# Carrega as bases (mesma estrutura do seu script)
# =============================================================================
purchase_events     = pd.read_csv(os.path.join(RAW, 'purchase_events.csv'))
product_item_events = pd.read_csv(os.path.join(RAW, 'product_item_events.csv'))
extra_info_events   = pd.read_csv(os.path.join(RAW, 'extra_info_events.csv'))


# =============================================================================
# Normaliza tipos
# =============================================================================
for df in (purchase_events, product_item_events, extra_info_events):
    df['transaction_datetime'] = pd.to_datetime(df['transaction_datetime'])
    df['transaction_date']     = pd.to_datetime(df['transaction_date']).dt.date

for c in ('order_date', 'release_date'):
    purchase_events[c] = pd.to_datetime(purchase_events[c], errors='coerce').dt.date


# =============================================================================
# PASSO 1: Último evento do dia por (purchase_id, transaction_date)
# =============================================================================
def last_of_day(df, extra_cols):
    """Mantém apenas o último evento do dia por compra (regra do enunciado)."""
    df2 = df.sort_values('transaction_datetime').drop_duplicates(
        subset=['purchase_id', 'transaction_date'], keep='last')
    return df2[['purchase_id', 'transaction_date'] + extra_cols]


p_day  = last_of_day(purchase_events, [
    'buyer_id', 'prod_item_id', 'order_date', 'release_date', 'producer_id',
    'purchase_total_value', 'purchase_status',
    'purchase_partition', 'prod_item_partition'
])
pi_day = last_of_day(product_item_events, [
    'product_id', 'purchase_value'
])
ei_day = last_of_day(extra_info_events, [
    'subsidiary'
])


# =============================================================================
# PASSO 2: Esqueleto — união dos pares (purchase_id, transaction_date)
# =============================================================================
sk = pd.concat([
    p_day [['purchase_id','transaction_date']].assign(has_purchase=1, has_product_item=0, has_extra_info=0),
    pi_day[['purchase_id','transaction_date']].assign(has_purchase=0, has_product_item=1, has_extra_info=0),
    ei_day[['purchase_id','transaction_date']].assign(has_purchase=0, has_product_item=0, has_extra_info=1),
], ignore_index=True).groupby(['purchase_id','transaction_date'], as_index=False).max()


# =============================================================================
# PASSO 3: Join do esqueleto com as 3 fontes
# =============================================================================
j = sk.merge(p_day,  on=['purchase_id','transaction_date'], how='left') \
      .merge(pi_day, on=['purchase_id','transaction_date'], how='left') \
      .merge(ei_day, on=['purchase_id','transaction_date'], how='left')


# =============================================================================
# PASSO 4: Forward fill por purchase_id ordenado por transaction_date
# =============================================================================
# IMPORTANTE: ordenar por (purchase_id, transaction_date) ANTES do ffill.
# O ffill propaga o último valor não-nulo "para baixo" dentro de cada grupo.
#
# Inclui purchase_status no ffill — assim cancelamentos retroativos
# (mudança de APROVADA → CANCELADA num evento futuro) são propagados.
j = j.sort_values(['purchase_id', 'transaction_date']).reset_index(drop=True)

ffill_cols = [
    'buyer_id', 'prod_item_id', 'order_date', 'release_date', 'producer_id',
    'purchase_total_value', 'purchase_status',
    'purchase_partition', 'prod_item_partition',
    'product_id', 'purchase_value',
    'subsidiary'
]
j[ffill_cols] = j.groupby('purchase_id')[ffill_cols].ffill()


# =============================================================================
# PASSO 5: is_current + is_gmv_eligible + updated_sources + etl_loaded_at
# =============================================================================
# is_current: TRUE apenas no snapshot mais recente de cada purchase_id
max_td = j.groupby('purchase_id')['transaction_date'].transform('max')
j['is_current'] = (j['transaction_date'] == max_td)

# is_gmv_eligible: regra de negócio encapsulada (paga + aprovada)
j['is_gmv_eligible'] = (
    j['release_date'].notna() &
    (j['purchase_status'] == 'APROVADA')
)

# updated_sources: quais fontes dispararam a linha (auditoria)
def sources(row):
    out = []
    if row['has_purchase']:     out.append('purchase')
    if row['has_product_item']: out.append('product_item')
    if row['has_extra_info']:   out.append('purchase_extra_info')
    return ','.join(out)

j['updated_sources'] = j.apply(sources, axis=1)
j['etl_loaded_at']   = datetime.now().replace(microsecond=0)


# =============================================================================
# Seleção e ordem final das colunas
# =============================================================================
final_cols = [
    'transaction_date', 'purchase_id',
    'buyer_id', 'prod_item_id', 'order_date', 'release_date', 'producer_id',
    'purchase_total_value', 'purchase_status',
    'purchase_partition', 'prod_item_partition',
    'product_id', 'purchase_value',
    'subsidiary',
    'is_current', 'is_gmv_eligible', 'updated_sources', 'etl_loaded_at'
]
fct = j[final_cols].copy()


# =============================================================================
# OUTPUT
# =============================================================================
pd.set_option('display.width', 220)
pd.set_option('display.max_columns', None)

print("=" * 120)
print("DATASET FINAL POPULADO — analytics.fct_purchase_history")
print("=" * 120)
# Print resumido (todas as colunas vão pro CSV)
cols_print = ['transaction_date','purchase_id','release_date','purchase_status',
              'purchase_value','subsidiary',
              'is_current','is_gmv_eligible','updated_sources']
print(fct[cols_print].to_string(index=False))
print()

# Salva
out_path = os.path.join(SPEC, 'fct_purchase_history.csv')
fct.to_csv(out_path, index=False)
print(f"✅ Salvo em: {out_path}")
print(f"   Total de linhas: {len(fct)}")