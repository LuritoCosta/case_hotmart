"""
=============================================================================
DESAFIO TÉCNICO HOTMART - ANALYTICS ENGINEER
app/app.py — Orquestrador
=============================================================================
Executa os 2 scripts em sequência:
    1) src/01_gerar_bases.py          — gera CSVs em data/raw/
    2) src/03_simulacao_etl.py        — ETL fct_purchase_history

Para um pipeline real este orquestrador seria substituído por Airflow,
Dagster ou Prefect — o ponto de cada step e suas dependências fica
explícito aqui pra fins de demonstração e reprodutibilidade local.

Uso:
    cd case_hotmart/
    python app/app.py                  # roda tudo
    python app/app.py --only-etl       # roda só o ETL
=============================================================================
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

# Resolve caminhos relativos à raiz do projeto (case_hotmart/)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC  = os.path.join(ROOT, 'src')


# Cada step é uma tupla (nome, caminho_do_script, descrição)
STEPS = [
    ('gerar_bases',    os.path.join(SRC, '01_gerar_bases.py'),
     'Gera CSVs raw a partir dos dados de exemplo do PDF'),
    ('etl',            os.path.join(SRC, '03_simulacao_etl.py'),
     'Constrói fct_purchase_history (5 passos com forward fill)'),
]


def run_step(name: str, script: str, description: str) -> bool:
    """Executa um script Python e retorna True se sucesso."""
    print()
    print('━' * 80)
    print(f'▶  STEP {name}')
    print(f'   {description}')
    print(f'   script: {os.path.relpath(script, ROOT)}')
    print('━' * 80)

    inicio = time.time()
    result = subprocess.run(
        [sys.executable, script],
        cwd=os.path.dirname(script),  # roda dentro de src/ para que os
                                       # caminhos relativos '../data/...'
                                       # funcionem como nos scripts originais
    )
    duracao = time.time() - inicio

    if result.returncode == 0:
        print(f'\n✅  STEP {name} concluído em {duracao:.1f}s')
        return True
    else:
        print(f'\n❌  STEP {name} FALHOU (exit code {result.returncode})')
        return False


def main():
    parser = argparse.ArgumentParser(description='Orquestrador do case Hotmart')
    parser.add_argument('--skip-etl', action='store_true',
                        help='Pula o ETL')
    parser.add_argument('--only-etl', action='store_true',
                        help='Roda apenas o ETL (e a geração de bases)')
    args = parser.parse_args()

    # Filtra steps conforme flags
    steps_to_run = list(STEPS)
    if args.only_etl:
        steps_to_run = [s for s in STEPS if s[0] in ('gerar_bases', 'etl')]
    if args.skip_etl:
        steps_to_run = [s for s in steps_to_run if s[0] != 'etl']

    print()
    print('=' * 80)
    print(f'  CASE HOTMART — Pipeline iniciado em {datetime.now():%Y-%m-%d %H:%M:%S}')
    print(f'  {len(steps_to_run)} step(s) a executar')
    print('=' * 80)

    falhas = []
    for name, script, description in steps_to_run:
        if not run_step(name, script, description):
            falhas.append(name)
            # Se geração de bases falhou, não adianta rodar o resto
            if name == 'gerar_bases':
                break

    print()
    print('=' * 80)
    if not falhas:
        print(f'  ✅  Pipeline concluído com sucesso ({len(steps_to_run)}/{len(steps_to_run)} steps)')
    else:
        print(f'  ⚠️   Pipeline concluído com falhas em: {", ".join(falhas)}')
    print('=' * 80)

    sys.exit(1 if falhas else 0)


if __name__ == '__main__':
    main()