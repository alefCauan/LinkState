import os
import json
import heapq
import threading
import time
import sys
import socket
import subprocess
import datetime
import psutil
import ipaddress

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("Router script started.")

# Step 1: Create a print lock for thread-safe logging
print_lock = threading.Lock()

def print2(string: str):
    with print_lock:
        print(f"[{router_id}] {string}")

# Step 2: Define the LSDB class
class LSDB:
    def __init__(self, router_id: str, neighbors_ip: dict):
        self.router_id = router_id
        self.neighbors_ip = neighbors_ip  # Recognized neighbors (bidirectional) with their IPs
        self.tabela = {}  # Link State Database (LSDB)
        self.roteamento = {}  # Routing table (destination -> next hop)
        self.tempo_inicio = time.time()
        self.quantidade_roteadores = 0

    def criar_entrada(self, sequence_number: int, timestamp: float, addresses: list, links: dict) -> dict:
        return {
            "sequence_number": sequence_number,
            "timestamp": timestamp,
            "addresses": addresses,
            "links": links,
        }

    def atualizar(self, pacote: dict) -> bool:
        router_id = pacote["router_id"]
        sequence_number = pacote["sequence_number"]
        entrada = self.tabela.get(router_id)

        # Ignore outdated or duplicate LSAs
        if entrada and sequence_number <= entrada["sequence_number"]:
            return False

        # Update the LSDB with the new LSA
        self.tabela[router_id] = self.criar_entrada(
            sequence_number, pacote["timestamp"], pacote["addresses"], pacote["links"]
        )

        # Check for new routers in the links
        for vizinho in pacote["links"].keys():
            if vizinho not in self.tabela:
                print2(f"[LSDB] Discovered new router: {vizinho}")
                self.tabela[vizinho] = self.criar_entrada(-1, 0, [], {})

        # Update convergence tracking
        quantidade_roteadores = len(self.tabela.keys())
        if quantidade_roteadores > self.quantidade_roteadores:
            if quantidade_roteadores == (len(self.roteamento) + 1):
                self.quantidade_roteadores = quantidade_roteadores
                tempo_convergencia = time.time() - self.tempo_inicio
                data_formatada = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                try:
                    with open("convergencia.txt", "w") as file:
                        file.write(
                            f"[{data_formatada}] {self.router_id}: {tempo_convergencia:.2f} seconds [{quantidade_roteadores} routers]\n"
                        )
                except Exception as e:
                    print2(f"[ERROR] Failed to write convergence time: {e}")

        # Compute shortest paths and update routing table
        caminhos = self.dijkstra()
        self.atualizar_proximo_pulo(caminhos)
        self.atualizar_rotas()
        return True

    def dijkstra(self) -> dict:
        distances = {router: float("infinity") for router in self.tabela}
        distances[self.router_id] = 0
        predecessors = {router: None for router in self.tabela}
        pq = [(0, self.router_id)]
        visited = set()

        while pq:
            current_distance, current_router = heapq.heappop(pq)
            if current_router in visited:
                continue
            visited.add(current_router)
            for neighbor, weight in self.tabela[current_router]["links"].items():
                distance = current_distance + weight
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    predecessors[neighbor] = current_router
                    heapq.heappush(pq, (distance, neighbor))
        
        return predecessors

    def atualizar_proximo_pulo(self, caminhos: dict):
        self.roteamento = {}
        for destino in caminhos.keys():
            if destino != self.router_id:
                pulo = destino
                while pulo is not None and caminhos[pulo] != self.router_id:
                    pulo = caminhos[pulo]
                if pulo is not None:  # Ensure there's a path
                    self.roteamento[destino] = pulo
        self.roteamento = dict(sorted(self.roteamento.items()))

    def atualizar_rotas(self):
        for roteador_destino, roteador_gateway in list(self.roteamento.items()):
            if roteador_destino != self.router_id:
                if roteador_gateway not in self.neighbors_ip:
                    print2(f"[LSDB] Ignoring route to {roteador_destino} via {roteador_gateway}: gateway not recognized yet")
                    continue
                for ip_destino in self.tabela[roteador_destino]["addresses"]:
                    ip_gateway = self.neighbors_ip[roteador_gateway]
                    comando = ["ip", "route", "replace", ip_destino, "via", ip_gateway]
                    try:
                        subprocess.run(comando, check=True)
                        print2(f"Route added: {ip_destino} -> {ip_gateway} [{roteador_gateway}]")
                    except subprocess.CalledProcessError as e:
                        print2(f"[ERROR] Failed to add route: {comando} -> {e} ({self.router_id} -> {roteador_gateway})")

# Step 3: Define the HelloSender class
class HelloSender:
    def __init__(self, router_id: str, interfaces: list, neighbors_detected: dict):
        self.router_id = router_id
        self.interfaces = interfaces
        self.neighbors_detected = neighbors_detected
        self.interval = 5  # Send HELLO every 5 seconds

    def send_hello(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            packet = {
                "type": "HELLO",
                "router_id": self.router_id,
                "known_neighbors": list(self.neighbors_detected.keys())
            }
            packet_data = json.dumps(packet).encode("utf-8")
            for interface in self.interfaces:
                if "broadcast" in interface:
                    try:
                        sock.sendto(packet_data, (interface["broadcast"], 5000))
                        print2(f"Sent HELLO to {interface['broadcast']}")
                    except Exception as e:
                        print2(f"[ERROR] Failed to send HELLO to {interface['broadcast']}: {e}")
            time.sleep(self.interval)

    def start(self):
        thread = threading.Thread(target=self.send_hello, daemon=True)
        thread.start()

# Step 4: Define the LSASender class
class LSASender:
    def __init__(self, router_id: str, neighbors_ip: dict, neighbors_cost: dict, interfaces: list, lsdb: LSDB):
        self.router_id = router_id
        self.neighbors_ip = neighbors_ip
        self.neighbors_cost = neighbors_cost
        self.interfaces = interfaces
        self.lsdb = lsdb
        self.sequence_number = 0
        self.interval = 10  # Send LSA every 10 seconds

    def send_lsa(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            addresses = [iface["address"] for iface in self.interfaces]
            links = {neighbor: cost for neighbor, cost in self.neighbors_cost.items()}
            packet = {
                "type": "LSA",
                "router_id": self.router_id,
                "sequence_number": self.sequence_number,
                "timestamp": time.time(),
                "addresses": addresses,
                "links": links
            }
            self.sequence_number += 1
            packet_data = json.dumps(packet).encode("utf-8")
            for interface in self.interfaces:
                if "broadcast" in interface:
                    try:
                        sock.sendto(packet_data, (interface["broadcast"], 5000))
                        print2(f"Sent LSA to {interface['broadcast']}")
                    except Exception as e:
                        print2(f"[ERROR] Failed to send LSA to {interface['broadcast']}: {e}")
            time.sleep(self.interval)

    def forward_to_neighbors(self, packet: dict, sender_ip: str):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        packet_data = json.dumps(packet).encode("utf-8")
        for interface in self.interfaces:
            if "broadcast" in interface:
                try:
                    sock.sendto(packet_data, (interface["broadcast"], 5000))
                    print2(f"Forwarded LSA from {packet['router_id']} to {interface['broadcast']}")
                except Exception as e:
                    print2(f"[ERROR] Failed to forward LSA to {interface['broadcast']}: {e}")

    def start(self):
        thread = threading.Thread(target=self.send_lsa, daemon=True)
        thread.start()

# Step 5: Define the NeighborManager class
class NeighborManager:
    def __init__(self, router_id: str, lsa_sender: LSASender, lsdb: LSDB):
        self.router_id = router_id
        self.lsa_sender = lsa_sender
        self.lsdb = lsdb
        self.neighbors_detected = lsa_sender.neighbors_cost
        self.neighbors_recognized = lsa_sender.neighbors_ip

    def process_hello(self, packet: dict, sender_ip: str):
        sender_id = packet["router_id"]
        known_neighbors = packet["known_neighbors"]
        self.neighbors_detected[sender_id] = self.get_cost(self.router_id, sender_id)
        if self.router_id in known_neighbors and sender_id not in self.neighbors_recognized:
            self.neighbors_recognized[sender_id] = sender_ip
            self.lsa_sender.start()
            print2(f"Recognized bidirectional neighbor: {sender_id} at {sender_ip}")

    def process_lsa(self, packet: dict, sender_ip: str):
        valid_packet = self.lsdb.atualizar(packet)
        if valid_packet:
            self.lsa_sender.forward_to_neighbors(packet, sender_ip)

    def get_cost(self, router_id: str, neighbor_id: str) -> int:
        # Map your environment variables to the format expected by the working implementation
        cost = os.getenv(f"CONNECTED_TO_ROUTER_{neighbor_id}")
        if cost is None:
            cost = 1  # Default cost if not specified
        return int(cost)

# Step 6: Define the Router class
class Router:
    def __init__(self, router_id: str, port: int = 5000, buffer_size: int = 4096):
        self.router_id = router_id
        self.interfaces = self.list_interfaces()
        self.port = port
        self.buffer_size = buffer_size
        self.neighbors_detected = {}
        self.neighbors_recognized = {}
        self.hello_sender = HelloSender(self.router_id, self.interfaces, self.neighbors_detected)
        self.lsdb = LSDB(self.router_id, self.neighbors_recognized)
        self.lsa_sender = LSASender(
            self.router_id, self.neighbors_recognized, self.neighbors_detected, self.interfaces, self.lsdb
        )
        self.neighbor_manager = NeighborManager(self.router_id, self.lsa_sender, self.lsdb)

    def list_interfaces(self) -> list:
        interfaces = psutil.net_if_addrs()
        interfaces_list = []
        for interface, addresses in interfaces.items():
            if interface.startswith("eth"):
                for address in addresses:
                    if address.family == socket.AF_INET:
                        if address.broadcast:
                            interfaces_list.append({
                                "address": address.address,
                                "broadcast": address.broadcast
                            })
                        else:
                            ip = ipaddress.ip_address(address.address)
                            rede = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                            interfaces_list.append({"address": f"{rede.network_address}/24"})
        return interfaces_list

    def receive_packets(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", self.port))
        while True:
            try:
                data, addr = sock.recvfrom(self.buffer_size)
                message = data.decode("utf-8")
                packet = json.loads(message)
                packet_type = packet.get("type")
                sender_id = packet.get("router_id")
                if sender_id != self.router_id:
                    sender_ip = addr[0]
                    print2(f"Received {packet_type} packet from {sender_ip} [{sender_id}]")
                    if packet_type == "HELLO":
                        self.neighbor_manager.process_hello(packet, sender_ip)
                    elif packet_type == "LSA":
                        self.neighbor_manager.process_lsa(packet, sender_ip)
            except Exception as e:
                print2(f"Error receiving packet: {e}")

    def start(self):
        thread = threading.Thread(target=self.receive_packets, daemon=True)
        thread.start()
        self.hello_sender.start()
        while True:
            time.sleep(1)

# Step 7: Main execution
if __name__ == "__main__":
    router_id = os.getenv("CONTAINER_NAME")
    if not router_id:
        print("Error: CONTAINER_NAME environment variable not found")
        sys.exit(1)

    # Set router_id for print2 function
    router_id = router_id
    print2("Starting router...")
    router = Router(router_id)
    router.start()