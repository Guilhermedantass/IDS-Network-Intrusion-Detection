"""Resumo das execucoes gravadas no SQLite."""
from datetime import datetime

from . import storage


def _hora(ts):
    return datetime.fromtimestamp(ts).strftime('%d/%m %H:%M:%S') if ts else '-'


def list_runs(db_path=storage.DB_PATH, limit=10):
    conn = storage.connect(db_path)
    rows = conn.execute('SELECT id, source, started_at, flows, attacks FROM runs '
                        'ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    print(f'{"run":>4}  {"inicio":<15}  {"fluxos":>8}  {"ataques":>8}  origem')
    for run_id, source, started, flows, attacks in rows:
        print(f'{run_id:>4}  {_hora(started):<15}  {flows or 0:>8,}  {attacks or 0:>8,}  {source}')


def summary(run_id=None, db_path=storage.DB_PATH, top=10):
    """Imprime o resumo de uma execucao (a ultima, se run_id for None)."""
    conn = storage.connect(db_path)
    if run_id is None:
        row = conn.execute('SELECT MAX(id) FROM runs').fetchone()
        run_id = row[0]
        if run_id is None:
            print('Nenhuma execucao no banco ainda.')
            return
    source, started, finished = conn.execute(
        'SELECT source, started_at, finished_at FROM runs WHERE id = ?', (run_id,)).fetchone()

    print(f'\n=== Execucao {run_id}: {source}')
    print(f'    {_hora(started)} -> {_hora(finished)}')

    tipos = conn.execute('SELECT attack_type, COUNT(*) FROM flows WHERE run_id = ? '
                         'GROUP BY 1 ORDER BY 2 DESC', (run_id,)).fetchall()
    total = sum(n for _, n in tipos)
    print(f'\n    {total:,} fluxos')
    for tipo, n in tipos:
        print(f'    {tipo:<14} {n:>9,}  ({n / total:.1%})')

    grupos = conn.execute('''
        SELECT attack_type, src_ip, dst_ip, COUNT(*), COUNT(DISTINCT dst_port), MIN(ts), MAX(ts),
               MAX(COALESCE(detected_by, 'modelo') LIKE 'modelo%'), MAX(detected_by LIKE '%volume')
        FROM flows WHERE run_id = ? AND is_attack = 1
        GROUP BY 1, 2, 3 ORDER BY 4 DESC LIMIT ?''', (run_id, top)).fetchall()
    conn.close()
    if not grupos:
        print('\n    Nenhum ataque detectado.')
        return
    print('\n    Principais origens de ataque:')
    print(f'    {"tipo":<13} {"origem":<16} {"destino":<16} {"fluxos":>7} {"portas":>7}  {"detectado por":<14} periodo')
    for tipo, src, dst, n, portas, ini, fim, por_modelo, por_volume in grupos:
        detector = '+'.join(nome for nome, sim in (('modelo', por_modelo), ('volume', por_volume)) if sim)
        print(f'    {tipo:<13} {src:<16} {dst:<16} {n:>7,} {portas:>7,}  {detector:<14} '
              f'{_hora(ini)} -> {_hora(fim)[-8:]}')
