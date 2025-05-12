import os
import json
import heapq
import threading
import time
import sys
import socket
import pickle

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("Router script started.")

# Step 1: Load the network topology
try:
    with open("/app/network_topology.json", "r") as f:
        topology = json.load(f)
        print("Successfully loaded network_topology.json")
except FileNotFoundError:
    print("Error: network_topology.json not found in /app.")
    sys.exit(1)
except json.JSONDecodeError:
    print("Error: network_topology.json is not a valid JSON file.")
    sys.exit(1)

# Step 2: Initialize the LSDB
class LSDB:
    def __init__(self, router_id, topology):
        self.router_id = router_id
        self.graph = {router_id: {}}  # Inicializa apenas com o próprio nó
        self.shortest_paths = {}
        self.costs = {}
        self.sequence_number = 0
        self.last_seen = {}
        self.timeout = 30
        self.neighbors = set()  # Vizinhos descobertos dinamicamente

    def add_neighbor(self, neighbor_id, weight=1):
        if neighbor_id not in self.graph:
            self.graph[neighbor_id] = {}
        self.graph[self.router_id][neighbor_id] = weight
        self.graph[neighbor_id][self.router_id] = weight
        self.neighbors.add(neighbor_id)

    def create_lsa_packet(self):
        self.sequence_number += 1
        return {
            'type': 'LSA',
            'sender': self.router_id,
            'sequence': self.sequence_number,
            'links': self.graph[self.router_id].copy()
        }

    def is_router_alive(self, router_id):
        if router_id not in self.last_seen:
            return False
        return (time.time() - self.last_seen[router_id]) < self.timeout

    def update_from_lsa(self, lsa_packet):
        sender = lsa_packet['sender']
        links = lsa_packet['links']
        sequence = lsa_packet['sequence']
        self.last_seen[sender] = time.time()
        if sender not in self.graph:
            self.graph[sender] = {}
        self.graph[sender] = links
        # Ensure the link is bidirectional with the same weight
        for neighbor, weight in links.items():
            if neighbor == self.router_id:
                self.graph[self.router_id][sender] = weight
        print(f"\n[LSA Update] From {sender} (seq: {sequence})")
        self.cleanup_dead_routers()
        print(f"[LSA Update] Current Graph State:")
        for node, edges in self.graph.items():
            print(f"  {node}: {edges}")

    def cleanup_dead_routers(self):
        current_time = time.time()
        dead_routers = []
        for router in list(self.graph.keys()):
            if router != self.router_id and not self.is_router_alive(router):
                dead_routers.append(router)
        for router in dead_routers:
            if router in self.graph:
                print(f"[Topology Change] Router {router} is dead, removing from graph")
                del self.graph[router]
            for r in self.graph:
                if router in self.graph[r]:
                    del self.graph[r][router]

    def dijkstra(self):
        distances = {router: float("infinity") for router in self.graph}
        distances[self.router_id] = 0
        predecessors = {router: None for router in self.graph}
        pq = [(0, self.router_id)]
        visited = set()

        while pq:
            current_distance, current_router = heapq.heappop(pq)
            if current_router in visited:
                continue
            visited.add(current_router)
            for neighbor, weight in self.graph[current_router].items():
                distance = current_distance + weight
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    predecessors[neighbor] = current_router
                    heapq.heappush(pq, (distance, neighbor))

        for router in self.graph:
            if router == self.router_id:
                continue
            path = []
            current = router
            while current is not None:
                path.append(current)
                current = predecessors[current]
            path.reverse()
            self.shortest_paths[router] = path
            self.costs[router] = distances[router]

    def print_routes(self):
        print(f"\n[Routing Table] {self.router_id}")
        print("Destination      Next Hop    Cost    Path")
        print("-" * 50)
        for router, path in self.shortest_paths.items():
            cost = self.costs[router]
            next_hop = path[1] if len(path) > 1 else path[0]
            print(f"{router:<15} {next_hop:<11} {cost:<7} {' -> '.join(path)}")

# --- NOVO: Descoberta dinâmica de vizinhos via HELLO ---

def hello_broadcast(router_id):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    hello_packet = pickle.dumps({'type': 'HELLO', 'sender': router_id})
    while True:
        sock.sendto(hello_packet, ('<broadcast>', 5001))
        time.sleep(5)

def hello_listener(lsdb):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 5001))
    while True:
        data, addr = sock.recvfrom(1024)
        try:
            pkt = pickle.loads(data)
            if pkt.get('type') == 'HELLO':
                sender = pkt.get('sender')
                if sender != lsdb.router_id:
                    weight = int(os.getenv(f'CONNECTED_TO_ROUTER_{sender}', 1))
                    lsdb.add_neighbor(sender, weight=weight)
                    lsdb.last_seen[sender] = time.time()
                    print(f"Discovered neighbor {sender} with weight {weight}")
        except Exception:
            continue

# --- FIM HELLO ---

def receive_link_state_packets(lsdb):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 5000))
    sock.settimeout(5)
    try:
        print(f"{lsdb.router_id}: Started receiving LSA packets...")
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                lsa_packet = pickle.loads(data)
                if lsa_packet['type'] == 'LSA':
                    print(f"Received LSA from {lsa_packet['sender']}")
                    lsdb.update_from_lsa(lsa_packet)
                    lsdb.dijkstra()
                    lsdb.print_routes()
            except socket.timeout:
                lsdb.cleanup_dead_routers()
                lsdb.dijkstra()
                lsdb.print_routes()
                continue
    except Exception as e:
        print(f"{lsdb.router_id}: Receive thread failed with error: {e}")
        sock.close()
        sys.exit(1)

def send_link_state_packets(lsdb):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        print(f"{lsdb.router_id}: Started sending LSA packets...")
        while True:
            lsa_packet = lsdb.create_lsa_packet()
            packet_data = pickle.dumps(lsa_packet)
            for neighbor in list(lsdb.neighbors):
                sock.sendto(packet_data, ('<broadcast>', 5000))
                print(f"Sent LSA broadcast for {neighbor}")
            time.sleep(10)
    except Exception as e:
        print(f"{lsdb.router_id}: Send thread failed with error: {e}")
        sock.close()
        sys.exit(1)

def get_router_id():
    connected_subnet = os.getenv('CONNECTED_TO_SUBNET')
    if not connected_subnet:
        print("Error: CONNECTED_TO_SUBNET environment variable not found")
        sys.exit(1)
    subnet_num = connected_subnet.split('_')[-1]
    router_id = f"R{subnet_num}"
    print(f"Determined router ID {router_id} from subnet {connected_subnet}")
    return router_id

def main():
    router_id = get_router_id()
    print(f"Determined router ID: {router_id}")
    lsdb = LSDB(router_id, topology)
    threading.Thread(target=hello_broadcast, args=(router_id,), daemon=True).start()
    threading.Thread(target=hello_listener, args=(lsdb,), daemon=True).start()
    receive_thread = threading.Thread(target=receive_link_state_packets, args=(lsdb,))
    send_thread = threading.Thread(target=send_link_state_packets, args=(lsdb,))
    receive_thread.daemon = True
    send_thread.daemon = True
    receive_thread.start()
    send_thread.start()
    while True:
        print(f"\n{router_id}: Calculating routes...")
        lsdb.dijkstra()
        lsdb.print_routes()
        time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Router failed with error: {e}")
        sys.exit(1)