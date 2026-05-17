"""
Network Manager — Skeleton UDP pour le multijoueur LAN.

Architecture : host-autoritaire, 20Hz tick, JSON.
Thread daemon recv → queue, send depuis le thread principal.
Jamais de NodePath dans le thread réseau.
"""

import socket
import threading
import time
from queue import Queue, Empty

from src.net_protocol import encode, decode, make_handshake, make_disconnect


class NetworkManager:
    """Gère la connexion UDP (host ou client)."""

    TICK_RATE = 20            # Hz — fréquence d'envoi du world state
    TICK_INTERVAL = 1.0 / TICK_RATE
    BUFFER_SIZE = 4096
    TIMEOUT = 5.0             # Secondes avant déconnexion silencieuse

    def __init__(self, mode="host", port=7777, host_ip="127.0.0.1"):
        """
        mode: "host" ou "client"
        port: port UDP
        host_ip: IP du host (ignoré en mode host)
        """
        self.mode = mode
        self.port = port
        self.host_ip = host_ip
        self.running = False

        self._recv_queue = Queue()
        self._send_queue = Queue()
        self._socket = None
        self._thread = None

        # Host: dict {addr: {id, name, last_seen}}
        self.clients = {}
        self._next_player_id = 1

        # Client: adresse du host
        self._host_addr = (host_ip, port)
        self.connected = False
        self.player_id = None

    # ============================================================
    # Lifecycle
    # ============================================================

    def start(self):
        """Démarre le socket et le thread recv."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.settimeout(0.1)

        if self.mode == "host":
            self._socket.bind(("0.0.0.0", self.port))
            print(f"[NET] Host listening on port {self.port}")
        else:
            self._socket.bind(("0.0.0.0", 0))  # Port éphémère
            print(f"[NET] Client connecting to {self.host_ip}:{self.port}")

        self.running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._thread.start()

        # Client: envoie handshake
        if self.mode == "client":
            self.send_to(make_handshake(), self._host_addr)

    def stop(self):
        """Arrête proprement la connexion."""
        if not self.running:
            return
        self.running = False

        # Envoie disconnect
        msg = make_disconnect()
        if self.mode == "client" and self._host_addr:
            self.send_to(msg, self._host_addr)
        elif self.mode == "host":
            for addr in list(self.clients.keys()):
                self.send_to(msg, addr)

        if self._thread:
            self._thread.join(timeout=1.0)
        if self._socket:
            self._socket.close()
            self._socket = None

        print("[NET] Stopped.")

    # ============================================================
    # Send / Recv (thread-safe)
    # ============================================================

    def send_to(self, msg, addr):
        """Envoie un message (dict) à une adresse (ip, port)."""
        if not self._socket or not self.running:
            return
        try:
            self._socket.sendto(encode(msg), addr)
        except OSError:
            pass

    def send_to_all_clients(self, msg):
        """Host: broadcast un message à tous les clients connectés."""
        for addr in list(self.clients.keys()):
            self.send_to(msg, addr)

    def send_to_host(self, msg):
        """Client: envoie un message au host."""
        if self._host_addr:
            self.send_to(msg, self._host_addr)

    def recv(self):
        """Récupère le prochain message reçu (non-bloquant). Retourne (msg, addr) ou None."""
        try:
            return self._recv_queue.get_nowait()
        except Empty:
            return None

    def recv_all(self):
        """Récupère tous les messages en attente. Retourne [(msg, addr), ...]."""
        messages = []
        while True:
            item = self.recv()
            if item is None:
                break
            messages.append(item)
        return messages

    # ============================================================
    # Thread recv (daemon)
    # ============================================================

    def _recv_loop(self):
        """Boucle de réception dans un thread séparé."""
        while self.running:
            try:
                data, addr = self._socket.recvfrom(self.BUFFER_SIZE)
                msg = decode(data)
                if msg is not None:
                    self._recv_queue.put((msg, addr))
            except socket.timeout:
                continue
            except OSError:
                break

    # ============================================================
    # Host: gestion des clients
    # ============================================================

    def register_client(self, addr, name="Player"):
        """Enregistre un nouveau client (appelé par le game loop)."""
        if addr not in self.clients:
            pid = self._next_player_id
            self._next_player_id += 1
            self.clients[addr] = {
                "id": pid,
                "name": name,
                "last_seen": time.time(),
            }
            print(f"[NET] Client registered: {name} (id={pid}) from {addr}")
            return pid
        return self.clients[addr]["id"]

    def unregister_client(self, addr):
        """Désenregistre un client."""
        if addr in self.clients:
            info = self.clients.pop(addr)
            print(f"[NET] Client disconnected: {info['name']} (id={info['id']})")

    def cleanup_stale_clients(self):
        """Déconnecte les clients silencieux (timeout)."""
        now = time.time()
        stale = [addr for addr, info in self.clients.items()
                 if now - info["last_seen"] > self.TIMEOUT]
        for addr in stale:
            self.unregister_client(addr)

    def touch_client(self, addr):
        """Met à jour le timestamp d'un client."""
        if addr in self.clients:
            self.clients[addr]["last_seen"] = time.time()
