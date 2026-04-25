"""
=============================================================================
DESAFIO TÉCNICO HOTMART - ANALYTICS ENGINEER
Script: 03_simulacao_etl.py
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
# DATA QUALITY GATE — ISO 25012
# =============================================================================
# ISO 25012 define 15 características de qualidade de dados. As 7 aplicáveis
# a este ETL são verificadas abaixo, organizadas por dimensão.
# Checks marcados como critical=True bloqueiam a carga se violados.
# =============================================================================

class DataQualityError(RuntimeError):
    pass


_VALID_STATUSES = {'APROVADA', 'INICIADA', 'CANCELADA', 'REEMBOLSADA', 'EXPIRADA'}


def _check(dimension: str, name: str, violations: int, total: int,
           critical: bool, threshold: float = 0.0) -> dict:
    pct = violations / total if total else 0.0
    passed = pct <= threshold
    return {
        'dimension': dimension,
        'check': name,
        'violations': violations,
        'total': total,
        'pct_violations': round(pct * 100, 2),
        'threshold_pct': threshold * 100,
        'passed': passed,
        'critical': critical,
    }


def run_data_quality_gate(df: pd.DataFrame) -> list[dict]:
    """
    Executa o Data Quality Gate conforme ISO 25012.
    Retorna lista de resultados por check.
    Levanta DataQualityError se algum check crítico falhar.
    """
    n = len(df)
    results = []

    # ------------------------------------------------------------------
    # 1. COMPLETENESS (ISO 25012 §4.15)
    #    Grau em que os dados possuem valores para todos os atributos
    #    exigidos no contexto de uso.
    #
    #    Distinção:
    #    - PK/chaves (purchase_id, transaction_date): nunca nulos em nenhuma linha.
    #    - Atributos de serving (buyer_id, purchase_status): nulos são legítimos
    #      em snapshots históricos anteriores à chegada da fonte (design forward-fill),
    #      mas NUNCA devem estar nulos no snapshot ativo (is_current=True).
    # ------------------------------------------------------------------
    pk_fields = ['purchase_id', 'transaction_date']
    for col in pk_fields:
        nulls = int(df[col].isna().sum())
        results.append(_check('Completeness', f'no_null:{col}', nulls, n,
                               critical=True))

    current = df[df['is_current'] == True]
    n_current = len(current)
    serving_fields = ['buyer_id', 'purchase_status']
    for col in serving_fields:
        nulls = int(current[col].isna().sum())
        results.append(_check('Completeness', f'no_null_current:{col}', nulls, n_current,
                               critical=True))

    optional_fill_fields = ['release_date', 'purchase_total_value', 'purchase_value', 'subsidiary']
    for col in optional_fill_fields:
        nulls = int(df[col].isna().sum())
        # Não bloqueante — NULL é válido (estratégia forward-fill documentada)
        results.append(_check('Completeness', f'fill_rate:{col}', nulls, n,
                               critical=False, threshold=1.0))

    # ------------------------------------------------------------------
    # 2. ACCURACY (ISO 25012 §4.3)
    #    Grau em que os dados representam corretamente o valor verdadeiro.
    # ------------------------------------------------------------------
    neg_total = int((df['purchase_total_value'].dropna() < 0).sum())
    results.append(_check('Accuracy', 'purchase_total_value>=0', neg_total, n,
                           critical=True))

    neg_value = int((df['purchase_value'].dropna() < 0).sum())
    results.append(_check('Accuracy', 'purchase_value>=0', neg_value, n,
                           critical=True))

    # order_date não pode ser posterior à transaction_date
    mask_order = (
        df['order_date'].notna() &
        (pd.to_datetime(df['order_date']) > pd.to_datetime(df['transaction_date']))
    )
    results.append(_check('Accuracy', 'order_date<=transaction_date',
                           int(mask_order.sum()), n, critical=True))

    # release_date >= order_date quando ambos presentes
    mask_release = (
        df['release_date'].notna() & df['order_date'].notna() &
        (pd.to_datetime(df['release_date']) < pd.to_datetime(df['order_date']))
    )
    results.append(_check('Accuracy', 'release_date>=order_date',
                           int(mask_release.sum()), n, critical=False))

    # ------------------------------------------------------------------
    # 3. CONSISTENCY (ISO 25012 §4.7)
    #    Grau em que os dados não apresentam contradições.
    # ------------------------------------------------------------------
    bad_status = int((df['purchase_status'].notna() &
                      ~df['purchase_status'].isin(_VALID_STATUSES)).sum())
    results.append(_check('Consistency', 'purchase_status_in_domain',
                           bad_status, n, critical=True))

    # is_gmv_eligible deve ser exatamente: release_date IS NOT NULL AND status == 'APROVADA'
    expected_gmv = df['release_date'].notna() & (df['purchase_status'] == 'APROVADA')
    gmv_mismatch = int((df['is_gmv_eligible'] != expected_gmv).sum())
    results.append(_check('Consistency', 'is_gmv_eligible_rule',
                           gmv_mismatch, n, critical=True))

    # Cada purchase_id deve ter exatamente 1 is_current = True
    current_counts = df.groupby('purchase_id')['is_current'].sum()
    bad_current = int((current_counts != 1).sum())
    results.append(_check('Consistency', 'one_is_current_per_purchase',
                           bad_current, df['purchase_id'].nunique(), critical=True))

    # ------------------------------------------------------------------
    # 4. CURRENTNESS / TIMELINESS (ISO 25012 §4.8)
    #    Grau em que os dados representam a variação temporal correta.
    # ------------------------------------------------------------------
    today = pd.Timestamp.today().normalize()
    future_dates = int((pd.to_datetime(df['transaction_date']) > today).sum())
    results.append(_check('Currentness', 'transaction_date_not_future',
                           future_dates, n, critical=True))

    # etl_loaded_at deve ter sido gerado na última hora
    stale_etl = int(
        (pd.Timestamp.now() - pd.to_datetime(df['etl_loaded_at'])).dt.total_seconds().gt(3600).sum()
    )
    results.append(_check('Currentness', 'etl_loaded_at_within_1h',
                           stale_etl, n, critical=False))

    # ------------------------------------------------------------------
    # 5. CREDIBILITY (ISO 25012 §4.6)
    #    Grau em que os dados são considerados verdadeiros e plausíveis.
    # ------------------------------------------------------------------
    duplicates = int(df.duplicated(subset=['purchase_id', 'transaction_date']).sum())
    results.append(_check('Credibility', 'no_duplicate_pk',
                           duplicates, n, critical=True))

    # purchase_total_value não deve exceder um teto razoável (heurística de negócio)
    CEILING = 1_000_000
    over_ceiling = int((df['purchase_total_value'].dropna() > CEILING).sum())
    results.append(_check('Credibility', f'purchase_total_value<={CEILING}',
                           over_ceiling, n, critical=False))

    # ------------------------------------------------------------------
    # 6. TRACEABILITY (ISO 25012 §4.17)
    #    Grau em que os dados fornecem trilha de auditoria de acesso
    #    e modificações.
    # ------------------------------------------------------------------
    empty_sources = int((df['updated_sources'].isna() | (df['updated_sources'] == '')).sum())
    results.append(_check('Traceability', 'updated_sources_not_empty',
                           empty_sources, n, critical=True))

    null_etl_ts = int(df['etl_loaded_at'].isna().sum())
    results.append(_check('Traceability', 'etl_loaded_at_populated',
                           null_etl_ts, n, critical=True))

    # ------------------------------------------------------------------
    # 7. COMPLIANCE (ISO 25012 §4.5)
    #    Grau em que os dados aderem a padrões, convenções e regras.
    # ------------------------------------------------------------------
    # GMV só pode ser True quando status é APROVADA
    gmv_sem_aprovada = int(
        (df['is_gmv_eligible'] & (df['purchase_status'] != 'APROVADA')).sum()
    )
    results.append(_check('Compliance', 'gmv_requires_aprovada',
                           gmv_sem_aprovada, n, critical=True))

    # GMV só pode ser True quando release_date está preenchida
    gmv_sem_release = int(
        (df['is_gmv_eligible'] & df['release_date'].isna()).sum()
    )
    results.append(_check('Compliance', 'gmv_requires_release_date',
                           gmv_sem_release, n, critical=True))

    # ------------------------------------------------------------------
    # Relatório
    # ------------------------------------------------------------------
    SEP = "-" * 120
    print()
    print("=" * 120)
    print("DATA QUALITY GATE — ISO 25012")
    print("=" * 120)
    print(f"{'Dimensão':<18} {'Check':<40} {'Violações':>10} {'Total':>8} {'%Viol':>8} {'Limiar%':>8} {'Status':>8}")
    print(SEP)

    critical_failures = []
    for r in results:
        status = "PASS" if r['passed'] else ("FAIL [CRÍTICO]" if r['critical'] else "WARN")
        print(f"{r['dimension']:<18} {r['check']:<40} {r['violations']:>10} {r['total']:>8} "
              f"{r['pct_violations']:>7.1f}% {r['threshold_pct']:>7.1f}% {status:>13}")
        if not r['passed'] and r['critical']:
            critical_failures.append(r)

    print(SEP)
    total_checks = len(results)
    passed_checks = sum(1 for r in results if r['passed'])
    print(f"Resultado: {passed_checks}/{total_checks} checks aprovados")

    if critical_failures:
        names = ', '.join(r['check'] for r in critical_failures)
        print(f"BLOQUEADO — checks críticos reprovados: {names}")
        print("=" * 120)
        raise DataQualityError(
            f"Data Quality Gate bloqueou a carga. Checks críticos reprovados: {names}"
        )

    print("APROVADO — todos os checks críticos passaram.")
    print("=" * 120)
    return results


run_data_quality_gate(fct)


# =============================================================================
# OUTPUT
# =============================================================================
pd.set_option('display.width', 220)
pd.set_option('display.max_columns', None)

print()
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
print(f"[OK] Salvo em: {out_path}")
print(f"   Total de linhas: {len(fct)}")