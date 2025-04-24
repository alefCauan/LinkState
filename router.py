import argparse
import socket
import threading
import time
import json
import netifaces
import subprocess

# Configurações globais
HELLO_PORT = 9998
LS_PORT = 9999
HELLO_INTERVAL = 5
LS_INTERVAL = 30
neighbors = {}
lsdb = {}
seq_num = 0

def get_interface_ips():
    """Obtém IPs de todas as interfaces de rede."""
    ips = {}
    for iface in netifaces.interfaces():
        if netifaces.AF_INET in netifaces.ifaddresses(iface):
            ip_info = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]
            ips[iface] = {'ip': ip_info['addr'], 'broadcast': ip_info.get('broadcast')}
    return ips

def send_hello(router_id, link_networks, interfaces):
    """Envia pacotes 'hello' em interfaces de link via UDP broadcast."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:
        for link in link_networks:
            for iface, info in interfaces.items():
                if info['ip'].startswith(link.split('/')[0].split('.')[0] + '.'):
                    if info['broadcast']:
                        msg = f"HELLO from {router_id}".encode()
                        sock.sendto(msg, (info['broadcast'], HELLO_PORT))
        time.sleep(HELLO_INTERVAL)

def receive_hello(router_id, link_networks):
    """Recebe pacotes 'hello' e atualiza lista de vizinhos."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', HELLO_PORT))
    while True:
        data, addr = sock.recvfrom(1024)
        msg = data.decode()
        if msg.startswith("HELLO from") and addr[0] != interfaces[list(interfaces.keys())[0]]['ip']:
            neighbor_id = msg.split("from ")[1]
            neighbors[neighbor_id] = addr[0]

def tcp_server(router_id):
    """Servidor TCP para receber pacotes de estado de link."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('', LS_PORT))
    server.listen(5)
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_connection, args=(conn, addr)).start()

def handle_connection(conn, addr):
    """Processa pacotes de estado de link recebidos."""
    global lsdb
    while True:
        data = conn.recv(1024)
        if not data:
            break
        packet = json.loads(data.decode())
        if packet['seq_num'] > lsdb.get(packet['router_id'], {}).get('seq_num', -1):
            lsdb[packet['router_id']] = packet
            forward_link_state(packet, addr[0])
    conn.close()

def forward_link_state(packet, received_from):
    """Reencaminha pacotes de estado de link para outros vizinhos."""
    for neighbor_id, ip in neighbors.items():
        if ip != received_from:
            send_ls_packet(ip, packet)

def send_ls_packet(ip, packet):
    """Envia um pacote de estado de link via TCP."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, LS_PORT))
        sock.send(json.dumps(packet).encode())
        sock.close()
    except Exception as e:
        print(f"Erro ao enviar para {ip}: {e}")

def send_link_state(router_id, subnet, link_networks):
    """Envia periodicamente o pacote de estado de link do roteador."""
    global seq_num
    while True:
        packet = {
            "router_id": router_id,
            "seq_num": seq_num,
            "neighbors": [{"router_id": nid, "cost": 1} for nid in neighbors],
            "subnetworks": [subnet]
        }
        lsdb[router_id] = packet
        for neighbor_ip in neighbors.values():
            send_ls_packet(neighbor_ip, packet)
        seq_num += 1
        time.sleep(LS_INTERVAL)

def update_routing_table(subnet):
    """Atualiza a tabela de roteamento (simplificada para a inicialização)."""
    # Para esta implementação inicial, apenas configuramos rotas básicas
    # Expanda com Dijkstra conforme o LSDB cresce
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="ID do roteador")
    parser.add_argument("--subnet", required=True, help="Sub-rede conectada")
    parser.add_argument("--link", action="append", default=[], help="Redes de link")
    args = parser.parse_args()

    interfaces = get_interface_ips()
    threading.Thread(target=send_hello, args=(args.id, args.link, interfaces)).start()
    threading.Thread(target=receive_hello, args=(args.id, args.link)).start()
    threading.Thread(target=tcp_server, args=(args.id,)).start()
    threading.Thread(target=send_link_state, args=(args.id, args.subnet, args.link)).start()

    while True:
        time.sleep(1)  # Mantém o processo principal vivo

