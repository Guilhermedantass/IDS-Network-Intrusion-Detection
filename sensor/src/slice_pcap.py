"""Recorta uma janela de tempo de um PCAP grande.

Le de um arquivo ou da entrada padrao ('-'), entao da para recortar durante o
download, sem salvar o arquivo inteiro em disco:

    curl -L <url-do-pcap> | python -m src.slice_pcap - recorte.pcap \
        --inicio 2017-07-07T13:50-03:00 --fim 2017-07-07T14:40-03:00

Horarios em ISO 8601; inclua o fuso (o CIC-IDS-2017 usa o horario de New
Brunswick, UTC-3 em julho). A leitura para assim que passa do fim da janela.
"""
import argparse
import sys
from datetime import datetime

import dpkt


def slice_pcap(src, dst, start=None, end=None):
    """Copia para `dst` os pacotes com timestamp em [start, end] (epoch, segundos)."""
    kept = seen = 0
    reader = dpkt.pcap.Reader(src)
    writer = dpkt.pcap.Writer(dst, linktype=reader.datalink())
    for ts, buf in reader:
        seen += 1
        if end is not None and ts > end:
            break
        if start is None or ts >= start:
            writer.writepkt(buf, ts=ts)
            kept += 1
        if seen % 1_000_000 == 0:
            print(f'\r{seen:,} pacotes lidos, {kept:,} mantidos', end='', file=sys.stderr, flush=True)
    print(f'\r{seen:,} pacotes lidos, {kept:,} mantidos', file=sys.stderr)
    return kept


def _epoch(text):
    if text is None:
        return None
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise SystemExit(f'Informe o fuso horario em {text!r} (ex.: 2017-07-07T13:50-03:00)')
    return moment.timestamp()


def main():
    parser = argparse.ArgumentParser(description='Recorta uma janela de tempo de um PCAP.')
    parser.add_argument('entrada', help="arquivo .pcap ou '-' para ler da entrada padrao")
    parser.add_argument('saida', help='arquivo .pcap de saida')
    parser.add_argument('--inicio', help='inicio da janela (ISO 8601 com fuso)')
    parser.add_argument('--fim', help='fim da janela (ISO 8601 com fuso)')
    args = parser.parse_args()

    src = sys.stdin.buffer if args.entrada == '-' else open(args.entrada, 'rb')
    with src, open(args.saida, 'wb') as dst:
        slice_pcap(src, dst, _epoch(args.inicio), _epoch(args.fim))


if __name__ == '__main__':
    main()
