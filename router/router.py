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

sys.stdout.reconfigure(line_buffering=True)

print("Router script started.")

__print_lock = threading.Lock()

class LSDB:
    """
    Link State Database (LSDB) for maintaining routing information in a link-state routing protocol.

    Attributes:
        __router_id (str): The identifier of the router.
        __neighbors_ip (dict): Mapping of neighbor router IDs to their IP addresses.
        __table (dict): The link-state database storing router entries.
        __routing (dict): Routing table mapping destinations to next hops.
        __tempo_inicio (float): Timestamp when the router started (for convergence timing).
        __router_quant (int): Number of known routers in the network.
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
        self.__table = {}
        self.__routing = {}
        self.__tempo_inicio = time.time()
        self.__router_quant = 0

    def __create_entry(self, sequence_number: int, timestamp: float, addresses: list, links: dict) -> dict:
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

    def update_lsdb(self, pacote: dict) -> bool:
        """
        Update the LSDB with a new LSA packet and recalculate routes.

        Args:
            pacote (dict): The LSA packet containing routing information.

        Returns:
            bool: True if the database was updated, False otherwise.
        """
        router_id = pacote["router_id"]
        sequence_number = pacote["sequence_number"]
        entrada = self.__table.get(router_id)
        print(f"[{self.__router_id}] Processing LSA from {router_id} (seq {sequence_number}, current seq {entrada['sequence_number'] if entrada else 'None'})")
        if entrada and sequence_number <= entrada["sequence_number"]:
            print(f"[{self.__router_id}] Ignoring old LSA from {router_id}")
            return False
        self.__table[router_id] = self.__create_entry(
            sequence_number, pacote["timestamp"], pacote["addresses"], pacote["links"]
        )
        print(f"[{self.__router_id}] Updated LSDB for {router_id} with addresses: {pacote['addresses']}")

        for vizinho in pacote["links"].keys():
            if vizinho not in self.__table:
                print(f"[LSDB] Discovered new router: {vizinho}")
                self.__table[vizinho] = self.__create_entry(-1, 0, [], {})

        self.__router_quant = len(self.__table.keys())
        paths = self.__dijkstra()
        self.__update_lsdb_next_jump(paths)
        self.__update_lsdb_routes()
        return True

    def __dijkstra(self) -> dict:
        """
        Run Dijkstra's algorithm to compute shortest paths from this router to all others.

        Returns:
            dict: A dictionary mapping each router to its predecessor in the shortest path.
        """
        distances = {router: float("infinity") for router in self.__table}
        distances[self.__router_id] = 0
        predecessors = {router: None for router in self.__table}
        pq = [(0, self.__router_id)]
        visited = set()
        print(f"[{self.__router_id}] Running Dijkstra. Initial distances: {distances}")
        while pq:
            current_distance, current_router = heapq.heappop(pq)
            if current_router in visited:
                continue
            visited.add(current_router)
            links = self.__table.get(current_router, {}).get("links", {})
            if not links:
                print(f"[{self.__router_id}] No links for router {current_router}")
            for neighbor, weight in links.items():
                if neighbor in self.__table:
                    distance = current_distance + weight
                    if distance < distances[neighbor]:
                        distances[neighbor] = distance
                        predecessors[neighbor] = current_router
                        heapq.heappush(pq, (distance, neighbor))
        print(f"[{self.__router_id}] Dijkstra completed. Predecessors: {predecessors}")
        return predecessors

    def __update_lsdb_next_jump(self, paths: dict) -> None:
        """
        Update the routing table with next-hop information based on shortest paths.

        Args:
            paths (dict): Dictionary mapping routers to their predecessors in shortest paths.
        """
        self.__routing = {}
        print(f"[{self.__router_id}] Updating next hops. Paths: {paths}")
        for destino in paths.keys():
            if destino != self.__router_id:
                pulo = destino
                while pulo is not None and paths[pulo] != self.__router_id:
                    pulo = paths[pulo]
                if pulo is not None:
                    self.__routing[destino] = pulo
        self.__routing = dict(sorted(self.__routing.items()))
        print(f"[{self.__router_id}] Updated routing table: {self.__routing}")

    def __update_lsdb_routes(self) -> None:
        """
        Update the system's routing table using the `ip route` command based on the routing table.
        """
        print(f"[{self.__router_id}] Updating routes. Current routing table: {self.__routing}")
        for router_destiny, router_gateway in list(self.__routing.items()):
            if router_destiny != self.__router_id:
                if router_gateway not in self.__neighbors_ip:
                    print(f"[LSDB] Ignoring route to {router_destiny} via {router_gateway}: gateway not recognized yet")
                    continue
                for ip_destiny in self.__table[router_destiny]["addresses"]:
                    if "/24" in ip_destiny:  # Ensure it's a network
                        ip_gateway = self.__neighbors_ip[router_gateway]
                        command = ["ip", "route", "replace", ip_destiny, "via", ip_gateway]
                        try:
                            result = subprocess.run(command, check=True, capture_output=True, text=True)
                            print(f"Route added successfully: {ip_destiny} -> {ip_gateway} [{router_gateway}] - Output: {result.stdout}")
                        except subprocess.CalledProcessError as e:
                            print(f"[ERROR] Failed to add route: {command} -> {e.stderr} ({self.__router_id} -> {router_gateway})")
                    else:
                        print(f"[WARNING] Skipping invalid destination: {ip_destiny} (not a /24 network)")

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
            addresses = []
            for iface in self.__interfaces:
                if "address" in iface and "/24" in iface["address"]:
                    addresses.append(iface["address"])
                elif "address" in iface:
                    ip = ipaddress.ip_address(iface["address"])
                    network = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                    addresses.append(str(network.network_address) + "/24")
            links = {neighbor: cost for neighbor, cost in self.__neighbors_cost.items()}
            print(f"[{self.__router_id}] Sending LSA with links: {links}")
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
                        print(f"Sent LSA to {interface['broadcast']} with addresses: {addresses}")
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
        self.__neighbors_detected = lsa_sender._LSASender__neighbors_cost  
        self.__neighbors_recognized = lsa_sender._LSASender__neighbors_ip  

    def process_hello(self, packet: dict, sender_ip: str) -> None:
        """
        Process a received HELLO packet to detect neighbors.

        Args:
            packet (dict): The HELLO packet containing neighbor information.
            sender_ip (str): The IP address of the sender.
        """
        sender_id = packet["router_id"]
        known_neighbors = packet["known_neighbors"]
        cost = self.__get_cost(self.__router_id, sender_id)
        print(f"[{self.__router_id}] Processing HELLO from {sender_id} with cost {cost}")
        self.__neighbors_detected[sender_id] = cost
        if self.__router_id in known_neighbors and sender_id not in self.__neighbors_recognized:
            self.__neighbors_recognized[sender_id] = sender_ip
            print(f"[{self.__router_id}] Recognized bidirectional neighbor: {sender_id} at {sender_ip}")
            self.__lsa_sender.start()

    def process_lsa(self, packet: dict, sender_ip: str) -> None:
        """
        Process a received LSA packet and forward it if necessary.

        Args:
            packet (dict): The LSA packet containing routing information.
            sender_ip (str): The IP address of the sender.
        """
        valid_packet = self.__lsdb.update_lsdb(packet)
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
        print(f"[{router_id}] Getting cost for {router_id} -> {neighbor_id}: cost={cost}")
        if cost is None:
            print(f"[WARNING] No cost found for {router_id} -> {neighbor_id}, defaulting to 1")
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
        if destination_id not in self.__lsdb._LSDB__routing:
            print(f"No route to destination {destination_id}")
            return

        next_hop = self.__lsdb._LSDB__routing[destination_id]
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
        
        destinations = [rid for rid in self.__lsdb._LSDB__routing.keys() if rid != self.__router_id]
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