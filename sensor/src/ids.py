"""Linha de comando do IDS.

    ./ids ao-vivo [-i INTERFACE] [--duracao S]   monitora a rede e mostra alertas
    ./ids teste-nmap [--syn]                     escaneia o proprio PC e mostra se o IDS detectou
    ./ids teste-flood [--udp]                    faz um flood no proprio PC e mostra se o IDS detectou
    ./ids arquivo CAPTURA.pcap                   analisa um arquivo de captura
    ./ids resumo [RUN] [--lista]                 resultado da ultima execucao (ou da RUN)
    ./ids servico --api URL                      fica ligado; a captura e controlada pelo dashboard

Com --api URL (ou a variavel IDS_API_URL), os alertas tambem vao para a API (POST URL/api/alerts).
"""
import argparse
import os
import shutil
import socket
import subprocess
import threading
import time

from . import report, service, storage
from .alerts import AlertSender
from .detect import Detector, run as run_file
from .live import LiveCapture, ask_sudo, default_interface, tcpdump_command


def make_sender(args):
    if not args.api:
        return None
    print(f'Enviando alertas para {args.api} (sensor: {args.sensor})')
    return AlertSender(args.api, args.sensor)


def close_sender(sender):
    if sender:
        sender.close()
        if sender.sent:
            print(f'{sender.sent:,} alerta(s) enviado(s) para a API')


def cmd_ao_vivo(args):
    interface = args.interface or default_interface()
    ask_sudo()
    sender = make_sender(args)
    detector = Detector(f'ao vivo ({interface})', args.db, sender=sender)
    print(f'Monitorando {interface}. Ctrl+C para parar.')
    if interface != 'lo':
        print('Dica: trafego para o proprio PC (127.0.0.1 ou o seu IP) passa pela interface lo, '
              'nao pela placa de rede. Para testar com nmap no proprio PC, use: ./ids ao-vivo -i lo')
    print()
    try:
        LiveCapture(tcpdump_command(interface), detector).run(duration=args.duracao)
    finally:
        detector.close()
        close_sender(sender)
    report.summary(detector.run_id, args.db)


def run_self_test(name, attack, args):
    """Captura na interface lo enquanto `attack()` roda em outra thread e mostra o resumo."""
    ask_sudo()
    sender = make_sender(args)
    detector = Detector(f'{name} (lo)', args.db, sender=sender)
    stop = threading.Event()

    def atacar():
        time.sleep(2)   # tempo para o tcpdump comecar a capturar
        attack()
        time.sleep(2)   # ultimos pacotes chegarem
        stop.set()

    threading.Thread(target=atacar, daemon=True).start()
    try:
        LiveCapture(tcpdump_command('lo'), detector).run(stop=stop)
    finally:
        detector.close()
        close_sender(sender)
    report.summary(detector.run_id, args.db)


def cmd_teste_nmap(args):
    if not shutil.which('nmap'):
        raise SystemExit('nmap nao encontrado. Instale com: sudo apt install nmap')
    scans = [['nmap', '-sT', '-p', args.portas, '127.0.0.1']]
    if args.syn:
        scans.append(['sudo', 'nmap', '-sS', '-p', args.portas, '127.0.0.1'])

    def atacar():
        for scan in scans:
            print(f'\r>>> {" ".join(scan)}' + ' ' * 30)
            subprocess.run(scan, stdout=subprocess.DEVNULL)

    print('Capturando na interface lo (127.0.0.1) e escaneando o proprio PC.\n')
    run_self_test('teste-nmap', atacar, args)


def flood(udp, seconds, rate, port=9):
    """Flood contra 127.0.0.1 em uma porta fechada (9 = discard): so gera trafego, nao afeta nada.

    `rate` limita os pacotes/s: sem limite passa de 100 mil/s e cada SYN vira um
    fluxo para o modelo classificar.
    """
    inicio = time.monotonic()
    sent = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_sock:
        while (agora := time.monotonic() - inicio) < seconds:
            if sent > agora * rate:
                time.sleep(0.001)
                continue
            if udp:
                udp_sock.sendto(b'x' * 64, ('127.0.0.1', port))
            else:
                # cada connect manda um SYN; a porta fechada responde RST na hora
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect_ex(('127.0.0.1', port))
            sent += 1
    return sent


def cmd_teste_flood(args):
    tipo = 'UDP' if args.udp else 'SYN'
    # UDP: todo o flood e um fluxo so, entao da para mandar mais sem pesar no modelo
    taxa = args.taxa or (10_000 if args.udp else 2000)

    def atacar():
        print(f'\r>>> {tipo} flood em 127.0.0.1:9 por {args.segundos:g}s, {taxa:,} pacotes/s' + ' ' * 30)
        print(f'\r>>> {flood(args.udp, args.segundos, taxa):,} pacotes enviados' + ' ' * 30)

    print(f'Capturando na interface lo (127.0.0.1) e fazendo um {tipo} flood no proprio PC.\n')
    run_self_test('teste-flood', atacar, args)


def cmd_arquivo(args):
    sender = make_sender(args)
    try:
        run_id = run_file(args.pcap, args.db, sender=sender)
    finally:
        close_sender(sender)
    report.summary(run_id, args.db)


def cmd_servico(args):
    if not args.api:
        raise SystemExit('O servico precisa da API: use --api http://localhost:8080 (ou a variavel IDS_API_URL).')
    service.run(args.api, args.sensor, args.db)


def cmd_resumo(args):
    if args.lista:
        report.list_runs(args.db)
    else:
        report.summary(args.run, args.db)


def main():
    parser = argparse.ArgumentParser(prog='ids', description='IDS - deteccao de intrusao em trafego de rede.')
    sub = parser.add_subparsers(dest='comando', required=True)
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument('--db', default=storage.DB_PATH, help='banco SQLite (padrao: results/ids.db)')
    comum.add_argument('--api', default=os.environ.get('IDS_API_URL'),
                       help='URL da API que recebe os alertas, ex.: http://localhost:8080 (padrao: $IDS_API_URL)')
    comum.add_argument('--sensor', default=os.environ.get('IDS_SENSOR', socket.gethostname()),
                       help='nome deste sensor na API (padrao: $IDS_SENSOR ou o nome do PC)')

    p = sub.add_parser('ao-vivo', parents=[comum], help='monitora a rede e mostra alertas em tempo real')
    p.add_argument('-i', '--interface', help='interface de rede (padrao: a da rota padrao)')
    p.add_argument('--duracao', type=float, help='para depois de N segundos')
    p.set_defaults(func=cmd_ao_vivo)

    p = sub.add_parser('teste-nmap', parents=[comum], help='escaneia o proprio PC com nmap e mostra se o IDS detectou')
    p.add_argument('--syn', action='store_true', help='tambem faz o scan SYN (sudo nmap -sS)')
    p.add_argument('--portas', default='1-1000', help='portas escaneadas (padrao: 1-1000)')
    p.set_defaults(func=cmd_teste_nmap)

    p = sub.add_parser('teste-flood', parents=[comum], help='faz um flood no proprio PC e mostra se o IDS detectou')
    p.add_argument('--udp', action='store_true', help='flood UDP (padrao: flood de conexoes TCP/SYN)')
    p.add_argument('--segundos', type=float, default=5, help='duracao do flood (padrao: 5)')
    p.add_argument('--taxa', type=int, help='pacotes por segundo (padrao: 2000 SYN, 10000 UDP)')
    p.set_defaults(func=cmd_teste_flood)

    p = sub.add_parser('arquivo', parents=[comum], help='analisa um arquivo .pcap')
    p.add_argument('pcap')
    p.set_defaults(func=cmd_arquivo)

    p = sub.add_parser('resumo', parents=[comum], help='mostra o resultado de uma execucao')
    p.add_argument('run', nargs='?', type=int, help='numero da execucao (padrao: a ultima)')
    p.add_argument('--lista', action='store_true', help='lista as execucoes')
    p.set_defaults(func=cmd_resumo)

    p = sub.add_parser('servico', parents=[comum],
                       help='fica ligado e inicia/para a captura quando o dashboard mandar (precisa de --api)')
    p.set_defaults(func=cmd_servico)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
