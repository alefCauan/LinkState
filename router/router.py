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

# Force unbuffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True)

print("Router script started.")

# Thread-safe print lock for logging
__print_lock = threading.Lock()

class LSDB:
    """
    Link State Database (LSDB) for maintaining routing information in a link-state routing protocol.

    Attributes:
        __router_id (str): The identifier of the router.
        __neighbors_ip (dict): Mapping of neighbor router IDs to their IP addresses.
        __tabela (dict): The link-state database storing router entries.
        __roteamento (dict): Routing table mapping destinations to next hops.
        __tempo_inicio (float): Timestamp when the router started (for convergence timing).
        __quantidade_roteadores (int): Number of known routers in the network.
    """

    def __init__(self, router_id: str, neighbors_ip: dict) -> None:
        """
        Initialize the LSDB with router-specific data.

        Args:
            router_id (str): The identifier of this router (e.g., 'r1').
            neighbors_ip (dict): Dictionary mapping neighbor router IDs to their IP addresses.
        """
        self.__router_id = router_id
        self.__neighbors_ip = neighbors_ip
        self.__tabela = {}
        self.__roteamento = {}
        self.__tempo_inicio = time.time()
        self.__quantidade_roteadores = 0

    def __criar_entrada(self, sequence_number: int, timestamp: float, addresses: list, links: dict) -> dict:
        """
        Create an entry for the link-state database.

        Args:
            sequence_number (int): Sequence number of the LSA packet.
            timestamp (float): Timestamp of the LSA packet.
            addresses (list): List of IP addresses associated with the router.
            links (dict): Dictionary mapping neighbor router IDs to link costs.

        Returns:
            dict: A dictionary representing the LSDB entry.
        """
        return {
            "sequence_number": sequence_number,
            "timestamp": timestamp,
            "addresses": addresses,
            "links": links,
        }

    def atualizar(self, pacote: dict) -> bool:
        """
        Update the LSDB with a new LSA packet and recalculate routes.

        Args:
            pacote (dict): The LSA packet containing routing information.

        Returns:
            bool: True if the database was updated, False otherwise.
        """
        router_id = pacote["router_id"]
        sequence_number = pacote["sequence_number"]
        entrada = self.__tabela.get(router_id)

        if entrada and sequence_number <= entrada["sequence_number"]:
            return False

        self.__tabela[router_id] = self.__criar_entrada(
            sequence_number, pacote["timestamp"], pacote["addresses"], pacote["links"]
        )

        for vizinho in pacote["links"].keys():
            if vizinho not in self.__tabela:
                print(f"[LSDB] Discovered new router: {vizinho}")
                self.__tabela[vizinho] = self.__criar_entrada(-1, 0, [], {})

        quantidade_roteadores = len(self.__tabela.keys())
        if quantidade_roteadores > self.__quantidade_roteadores:
            if quantidade_roteadores == (len(self.__roteamento) + 1):
                self.__quantidade_roteadores = quantidade_roteadores
                tempo_convergencia = time.time() - self.__tempo_inicio
                data_formatada = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                try:
                    with open("/app/convergencia.txt", "a") as file:
                        file.write(
                            f"[{data_formatada}] {self.__router_id}: {tempo_convergencia:.2f} seconds [{quantidade_roteadores} routers]\n"
                        )
                except Exception as e:
                    print(f"[ERROR] Failed to write convergence time: {e}")

        caminhos = self.__dijkstra()
        self.__atualizar_proximo_pulo(caminhos)
        self.__atualizar_rotas()
        return True

    def __dijkstra(self) -> dict:
        """
        Run Dijkstra's algorithm to compute shortest paths from this router to all others.

        Returns:
            dict: A dictionary mapping each router to its predecessor in the shortest path.
        """
        distances = {router: float("infinity") for router in self.__tabela}
        distances[self.__router_id] = 0
        predecessors = {router: None for router in self.__tabela}
        pq = [(0, self.__router_id)]
        visited = set()

        while pq:
            current_distance, current_router = heapq.heappop(pq)
            if current_router in visited:
                continue
            visited.add(current_router)
            for neighbor, weight in self.__tabela[current_router]["links"].items():
                distance = current_distance + weight
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    predecessors[neighbor] = current_router
                    heapq.heappush(pq, (distance, neighbor))
        
        return predecessors

    def __atualizar_proximo_pulo(self, caminhos: dict) -> None:
        """
        Update the routing table with next-hop information based on shortest paths.

        Args:
            caminhos (dict): Dictionary mapping routers to their predecessors in shortest paths.
        """
        self.__roteamento = {}
        for destino in caminhos.keys():
            if destino != self.__router_id:
                pulo = destino
                while pulo is not None and caminhos[pulo] != self.__router_id:
                    pulo = caminhos[pulo]
                if pulo is not None:
                    self.__roteamento[destino] = pulo
        self.__roteamento = dict(sorted(self.__roteamento.items()))

    def __atualizar_rotas(self) -> None:
        """
        Update the system's routing table using the `ip route` command based on the routing table.
        """
        for roteador_destino, roteador_gateway in list(self.__roteamento.items()):
            if roteador_destino != self.__router_id:
                if roteador_gateway not in self.__neighbors_ip:
                    print(f"[LSDB] Ignoring route to {roteador_destino} via {roteador_gateway}: gateway not recognized yet")
                    continue
                for ip_destino in self.__tabela[roteador_destino]["addresses"]:
                    ip_gateway = self.__neighbors_ip[roteador_gateway]
                    comando = ["ip", "route", "replace", ip_destino, "via", ip_gateway]
                    try:
                        subprocess.run(comando, check=True)
                        print(f"Route added: {ip_destino} -> {ip_gateway} [{roteador_gateway}]")
                    except subprocess.CalledProcessError as e:
                        print(f"[ERROR] Failed to add route: {comando} -> {e} ({self.__router_id} -> {roteador_gateway})")

class HelloSender:
    """
    Sends HELLO packets periodically to discover neighbors in the network.

    Attributes:
        __router_id (str): The identifier of the router.
        __interfaces (list): List of network interfaces for broadcasting HELLO packets.
        __neighbors_detected (dict): Dictionary of detected neighbors and their costs.
        __interval (float): Interval (in seconds) between HELLO packet transmissions.
    """

    def __init__(self, router_id: str, interfaces: list, neighbors_detected: dict) -> None:
        """
        Initialize the HelloSender with router-specific data.

        Args:
            router_id (str): The identifier of this router.
            interfaces (list): List of network interfaces for broadcasting.
            neighbors_detected (dict): Dictionary to store detected neighbors.
        """
        self.__router_id = router_id
        self.__interfaces = interfaces
        self.__neighbors_detected = neighbors_detected
        self.__interval = 5.0

    def __send_hello(self) -> None:
        """
        Send HELLO packets periodically to all broadcast addresses on the interfaces.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            packet = {
                "type": "HELLO",
                "router_id": self.__router_id,
                "known_neighbors": list(self.__neighbors_detected.keys())
            }
            packet_data = json.dumps(packet).encode("utf-8")
            for interface in self.__interfaces:
                if "broadcast" in interface:
                    try:
                        sock.sendto(packet_data, (interface["broadcast"], 5000))
                        print(f"Sent HELLO to {interface['broadcast']}")
                    except Exception as e:
                        print(f"[ERROR] Failed to send HELLO to {interface['broadcast']}: {e}")
            time.sleep(self.__interval)

    def start(self) -> None:
        """
        Start the HELLO packet sender in a separate thread.
        """
        thread = threading.Thread(target=self.__send_hello, daemon=True)
        thread.start()

class LSASender:
    """
    Sends and forwards LSA (Link State Advertisement) packets to propagate routing information.

    Attributes:
        __router_id (str): The identifier of the router.
        __neighbors_ip (dict): Mapping of neighbor router IDs to their IP addresses.
        __neighbors_cost (dict): Mapping of neighbor router IDs to link costs.
        __interfaces (list): List of network interfaces for broadcasting LSA packets.
        __lsdb (LSDB): The Link State Database instance for this router.
        __sequence_number (int): Sequence number for LSA packets.
        __interval (float): Interval (in seconds) between LSA packet transmissions.
    """

    def __init__(self, router_id: str, neighbors_ip: dict, neighbors_cost: dict, interfaces: list, lsdb: LSDB) -> None:
        """
        Initialize the LSASender with router-specific data.

        Args:
            router_id (str): The identifier of this router.
            neighbors_ip (dict): Dictionary mapping neighbor router IDs to their IP addresses.
            neighbors_cost (dict): Dictionary mapping neighbor router IDs to link costs.
            interfaces (list): List of network interfaces for broadcasting.
            lsdb (LSDB): The Link State Database instance.
        """
        self.__router_id = router_id
        self.__neighbors_ip = neighbors_ip
        self.__neighbors_cost = neighbors_cost
        self.__interfaces = interfaces
        self.__lsdb = lsdb
        self.__sequence_number = 0
        self.__interval = 10.0

    def __send_lsa(self) -> None:
        """
        Send LSA packets periodically to all broadcast addresses on the interfaces.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            addresses = [iface["address"] for iface in self.__interfaces]
            links = {neighbor: cost for neighbor, cost in self.__neighbors_cost.items()}
            packet = {
                "type": "LSA",
                "router_id": self.__router_id,
                "sequence_number": self.__sequence_number,
                "timestamp": time.time(),
                "addresses": addresses,
                "links": links
            }
            self.__sequence_number += 1
            packet_data = json.dumps(packet).encode("utf-8")
            for interface in self.__interfaces:
                if "broadcast" in interface:
                    try:
                        sock.sendto(packet_data, (interface["broadcast"], 5000))
                        print(f"Sent LSA to {interface['broadcast']}")
                    except Exception as e:
                        print(f"[ERROR] Failed to send LSA to {interface['broadcast']}: {e}")
            time.sleep(self.__interval)

    def forward_to_neighbors(self, packet: dict, sender_ip: str) -> None:
        """
        Forward an LSA packet to all neighbors.

        Args:
            packet (dict): The LSA packet to forward.
            sender_ip (str): The IP address of the sender.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        packet_data = json.dumps(packet).encode("utf-8")
        for interface in self.__interfaces:
            if "broadcast" in interface:
                try:
                    sock.sendto(packet_data, (interface["broadcast"], 5000))
                    print(f"Forwarded LSA from {packet['router_id']} to {interface['broadcast']}")
                except Exception as e:
                    print(f"[ERROR] Failed to forward LSA to {interface['broadcast']}: {e}")

    def start(self) -> None:
        """
        Start the LSA packet sender in a separate thread.
        """
        thread = threading.Thread(target=self.__send_lsa, daemon=True)
        thread.start()

class NeighborManager:
    """
    Manages neighbor discovery and LSA processing for the router.

    Attributes:
        __router_id (str): The identifier of the router.
        __lsa_sender (LSASender): The LSASender instance for forwarding LSAs.
        __lsdb (LSDB): The Link State Database instance.
        __neighbors_detected (dict): Dictionary of detected neighbors and their costs.
        __neighbors_recognized (dict): Dictionary of recognized neighbors and their IP addresses.
    """

    def __init__(self, router_id: str, lsa_sender: LSASender, lsdb: LSDB) -> None:
        """
        Initialize the NeighborManager with router-specific data.

        Args:
            router_id (str): The identifier of this router.
            lsa_sender (LSASender): The LSASender instance for forwarding LSAs.
            lsdb (LSDB): The Link State Database instance.
        """
        self.__router_id = router_id
        self.__lsa_sender = lsa_sender
        self.__lsdb = lsdb
        self.__neighbors_detected = lsa_sender.__neighbors_cost
        self.__neighbors_recognized = lsa_sender.__neighbors_ip

    def process_hello(self, packet: dict, sender_ip: str) -> None:
        """
        Process a received HELLO packet to detect neighbors.

        Args:
            packet (dict): The HELLO packet containing neighbor information.
            sender_ip (str): The IP address of the sender.
        """
        sender_id = packet["router_id"]
        known_neighbors = packet["known_neighbors"]
        self.__neighbors_detected[sender_id] = self.__get_cost(self.__router_id, sender_id)
        if self.__router_id in known_neighbors and sender_id not in self.__neighbors_recognized:
            self.__neighbors_recognized[sender_id] = sender_ip
            self.__lsa_sender.start()
            print(f"Recognized bidirectional neighbor: {sender_id} at {sender_ip}")

    def process_lsa(self, packet: dict, sender_ip: str) -> None:
        """
        Process a received LSA packet and forward it if necessary.

        Args:
            packet (dict): The LSA packet containing routing information.
            sender_ip (str): The IP address of the sender.
        """
        valid_packet = self.__lsdb.atualizar(packet)
        if valid_packet:
            self.__lsa_sender.forward_to_neighbors(packet, sender_ip)

    def __get_cost(self, router_id: str, neighbor_id: str) -> int:
        """
        Retrieve the link cost to a neighbor from environment variables.

        Args:
            router_id (str): The identifier of this router.
            neighbor_id (str): The identifier of the neighbor router.

        Returns:
            int: The cost of the link to the neighbor (default to 1 if not found).
        """
        cost = os.getenv(f"CONNECTED_TO_ROUTER_{neighbor_id}")
        if cost is None:
            cost = 1
        return int(cost)

class Router:
    """
    Main router class implementing a link-state routing protocol.

    Attributes:
        __router_id (str): The identifier of the router.
        __port (int): The port number for UDP communication.
        __buffer_size (int): Buffer size for receiving UDP packets.
        __interfaces (list): List of network interfaces.
        __neighbors_detected (dict): Dictionary of detected neighbors and their costs.
        __neighbors_recognized (dict): Dictionary of recognized neighbors and their IP addresses.
        __hello_sender (HelloSender): The HelloSender instance for neighbor discovery.
        __lsdb (LSDB): The Link State Database instance.
        __lsa_sender (LSASender): The LSASender instance for LSA propagation.
        __neighbor_manager (NeighborManager): The NeighborManager instance for neighbor handling.
    """

    def __init__(self, router_id: str, port: int = 5000, buffer_size: int = 4096) -> None:
        """
        Initialize the Router with its configuration.

        Args:
            router_id (str): The identifier of this router.
            port (int, optional): The port number for UDP communication. Defaults to 5000.
            buffer_size (int, optional): Buffer size for receiving UDP packets. Defaults to 4096.
        """
        self.__router_id = router_id
        self.__port = port
        self.__buffer_size = buffer_size
        self.__interfaces = self.__list_interfaces()
        self.__neighbors_detected = {}
        self.__neighbors_recognized = {}
        self.__hello_sender = HelloSender(self.__router_id, self.__interfaces, self.__neighbors_detected)
        self.__lsdb = LSDB(self.__router_id, self.__neighbors_recognized)
        self.__lsa_sender = LSASender(
            self.__router_id, self.__neighbors_recognized, self.__neighbors_detected, self.__interfaces, self.__lsdb
        )
        self.__neighbor_manager = NeighborManager(self.__router_id, self.__lsa_sender, self.__lsdb)

    def __list_interfaces(self) -> list:
        """
        List all network interfaces and their IP addresses.

        Returns:
            list: A list of dictionaries containing interface details (address, broadcast).
        """
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

    def send_data_packet(self, destination_id: str, message: str) -> None:
        """
        Send a data packet to a specific destination router.

        Args:
            destination_id (str): The identifier of the destination router.
            message (str): The message to send.
        """
        if destination_id not in self.__lsdb._LSDB__roteamento:
            print(f"No route to destination {destination_id}")
            return

        next_hop = self.__lsdb._LSDB__roteamento[destination_id]
        if next_hop not in self.__neighbors_recognized:
            print(f"Next hop {next_hop} not recognized")
            return

        packet = {
            "type": "DATA",
            "router_id": self.__router_id,
            "destination": destination_id,
            "message": message,
            "timestamp": time.time()
        }

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            next_hop_ip = self.__neighbors_recognized[next_hop]
            sock.sendto(json.dumps(packet).encode("utf-8"), (next_hop_ip, self.__port))
            print(f"Sent DATA packet to {destination_id} via {next_hop} [{next_hop_ip}]")
        except Exception as e:
            print(f"Error sending DATA packet: {e}")

    def __receive_packets(self) -> None:
        """
        Receive and process incoming packets (HELLO, LSA, DATA).
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", self.__port))
        while True:
            try:
                data, addr = sock.recvfrom(self.__buffer_size)
                message = data.decode("utf-8")
                packet = json.loads(message)
                packet_type = packet.get("type")
                sender_id = packet.get("router_id")
                if sender_id != self.__router_id:
                    sender_ip = addr[0]
                    print(f"Received {packet_type} packet from {sender_ip} [{sender_id}]")
                    if packet_type == "HELLO":
                        self.__neighbor_manager.process_hello(packet, sender_ip)
                    elif packet_type == "LSA":
                        self.__neighbor_manager.process_lsa(packet, sender_ip)
                    elif packet_type == "DATA":
                        destination_id = packet.get("destination")
                        message = packet.get("message")
                        print(f"Received DATA packet for {destination_id} with message: {message}")
                        if destination_id != self.__router_id:
                            self.send_data_packet(destination_id, message)
                        else:
                            print(f"DATA packet reached destination {self.__router_id}: {message}")
            except Exception as e:
                print(f"Error receiving packet: {e}")

    def start(self) -> None:
        """
        Start the router by initiating packet receiving and periodic sending tasks.
        """
        thread = threading.Thread(target=self.__receive_packets, daemon=True)
        thread.start()
        self.__hello_sender.start()
        
        time.sleep(10)  # Wait for network convergence
        
        destinations = [rid for rid in self.__lsdb._LSDB__roteamento.keys() if rid != self.__router_id]
        if destinations:
            while True:
                for dest in destinations:
                    self.send_data_packet(dest, f"Test message from {self.__router_id} to {dest}")
                    time.sleep(5)
        else:
            print("No destinations available for data packet testing")
            while True:
                time.sleep(1)

if __name__ == "__main__":
    """
    Main entry point for the router script. Initializes and starts the router.
    """
    router_id = os.getenv("CONTAINER_NAME")
    if not router_id:
        print("Error: CONTAINER_NAME environment variable not found")
        sys.exit(1)

    print("Starting router...")
    router = Router(router_id)
    router.start()