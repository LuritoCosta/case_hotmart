import pandas as pd
from datetime import datetime

#Carrega as bases
purchase_events = pd.read_csv(fr'../data/raw/purchase_events.csv')
product_item_events = pd.read_csv(fr'../data/raw/product_item_events.csv')
extra_info_events = pd.read_csv(fr'../data/raw/extra_info_events.csv')


# Normaliza tipos
for df in (purchase_events, product_item_events, extra_info_events):
    df['transaction_datetime'] = pd.to_datetime(df['transaction_datetime'])
    df['transaction_date']     = pd.to_datetime(df['transaction_date']).dt.date
for c in ('order_date','release_date'):
    purchase_events[c] = pd.to_datetime(purchase_events[c]).dt.date
 
 
# =============================================================================
# PASSO 1: Último evento do dia por (purchase_id, transaction_date)
# =============================================================================
def last_of_day(df, extra_cols):
    df2 = df.sort_values('transaction_datetime').drop_duplicates(
        subset=['purchase_id','transaction_date'], keep='last')
    return df2[['purchase_id','transaction_date'] + extra_cols]
 
p_day  = last_of_day(purchase_events,     ['buyer_id','prod_item_id','order_date','release_date','producer_id'])
pi_day = last_of_day(product_item_events, ['product_id','item_quantity','purchase_value'])
ei_day = last_of_day(extra_info_events,   ['subsidiary'])
 
 
# =============================================================================
# PASSO 2: Esqueleto — união dos pares (purchase_id, transaction_date)
# =============================================================================
sk = pd.concat([
    p_day[['purchase_id','transaction_date']].assign(has_purchase=1, has_product_item=0, has_extra_info=0),
    pi_day[['purchase_id','transaction_date']].assign(has_purchase=0, has_product_item=1, has_extra_info=0),
    ei_day[['purchase_id','transaction_date']].assign(has_purchase=0, has_product_item=0, has_extra_info=1),
], ignore_index=True).groupby(['purchase_id','transaction_date'], as_index=False).max()

# =============================================================================
# PASSO 3: Join do esqueleto com as 3 fontes
# =============================================================================
j = sk.merge(p_day, on=['purchase_id','transaction_date'], how='left') \
      .merge(pi_day, on=['purchase_id','transaction_date'], how='left') \
      .merge(ei_day, on=['purchase_id','transaction_date'], how='left')
 
 
# =============================================================================
# PASSO 4: Forward fill por purchase_id ordenado por transaction_date
# =============================================================================
j = j.sort_values(['purchase_id','transaction_date']).reset_index(drop=True)
 
ffill_cols = ['buyer_id','prod_item_id','order_date','release_date','producer_id',
              'product_id','item_quantity','purchase_value','subsidiary']
j[ffill_cols] = j.groupby('purchase_id')[ffill_cols].ffill()
 
 
# =============================================================================
# PASSO 5: is_current + updated_sources + etl_loaded_at
# =============================================================================
max_td = j.groupby('purchase_id')['transaction_date'].transform('max')
j['is_current'] = (j['transaction_date'] == max_td)
 
def sources(row):
    out = []
    if row['has_purchase']:     out.append('purchase')
    if row['has_product_item']: out.append('product_item')
    if row['has_extra_info']:   out.append('purchase_extra_info')
    return out
j['updated_sources'] = j.apply(sources, axis=1)
j['etl_loaded_at'] = datetime.now().replace(microsecond=0)
 
final_cols = ['transaction_date','purchase_id','buyer_id','prod_item_id',
              'order_date','release_date','producer_id','product_id',
              'item_quantity','purchase_value','subsidiary',
              'is_current','updated_sources','etl_loaded_at']
fct = j[final_cols].copy()
 
 
# =============================================================================
# OUTPUT
# =============================================================================
print("=" * 100)
print("DATASET FINAL POPULADO — analytics.fct_purchase_history")
print("=" * 100)
print(fct.to_string(index=False))
print()
 
# Salva um CSV com o exemplo populado
fct.to_csv(fr'../data/specialized/fct_purchase_history.csv', index=False)