import json
import logging
import threading
import http.server
import urllib.parse

import os
import sys

# Añadir la raíz del repositorio al path antes de hacer imports locales
REPO_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

BLUE = '\033[94m'
GREEN = '\033[92m'
CYAN = '\033[96m'
MAGENTA = '\033[95m'
YELLOW = '\033[93m'
RED = '\033[91m'
NC = '\033[0m'

from provisioning.jumpstart.baremetal import create_vms, apply_post_install_specs, start_virtualbox_vms
from provisioning.jumpstart.software_provisioner import provision_all_nodes

log = logging.getLogger('coordinator')
log.setLevel(logging.INFO)

class DeploymentState:
    def __init__(self):
        self.batch_size = 3
        self.pending_nodes = []
        self.in_progress_nodes = []
        self.completed_nodes = []
        self.status = "IDLE"  # Posibles estados: IDLE, PXE_INSTALLING, ANSIBLE_PROVISIONING
        self.become_password = None  # Contraseña sudo de los nodos, recibida al inicio del deploy
        self.lock = threading.Lock()

state = DeploymentState()
host_api_global = None

class CoordinatorHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        log.info(f"{self.client_address[0]} - {format % args}")

    def _respond(self, code, body):
        body_bytes = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/health':
            self._respond(200, '{"status": "ok", "message": "Coordinator active"}')
            return

        if parsed.path == '/node-ready':
            node_name = params.get('node', [None])[0]
            if not node_name:
                self._respond(400, '{"error": "node parameter required"}')
                return
            
            safe_name = ''.join(c for c in node_name if c.isalnum() or c in '-_')
            log.info(f"Callback recibido de PXE: '{safe_name}'")
            self._respond(200, '{"status": "ok"}')
            
            # Lanzamos el proceso del evento en background para no bloquear el HTTP Server
            threading.Thread(target=process_node_ready, args=(safe_name,), daemon=True).start()
            return

        self._respond(404, '{"error": "not found"}')

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path == '/start-batch-deploy':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._respond(400, '{"error": "Invalid JSON"}')
                return

            vms = data.get('vms', [])
            if not vms:
                self._respond(400, '{"error": "No VMs provided"}')
                return

            become_password = data.get('become_password') or None
            if not become_password:
                self._respond(400, '{"error": "become_password es obligatorio para el despliegue"}')
                return

            # Guardar la contraseña en el estado global para usarla cuando Ansible arranque
            with state.lock:
                state.become_password = become_password

            success, message = start_batch_deployment(vms)
            if success:
                self._respond(200, json.dumps({"status": "ok", "message": message}))
            else:
                self._respond(409, json.dumps({"error": message}))
            return

        if parsed.path == '/reset':
            reset_coordinator()
            self._respond(200, '{"status": "ok", "message": "Coordinador reseteado a IDLE"}')
            return

        if parsed.path == '/provision':
            with state.lock:
                if state.status == "ANSIBLE_PROVISIONING":
                    self._respond(409, '{"error": "Ya hay un aprovisionamiento de Ansible en curso."}')
                    return
                state.status = "ANSIBLE_PROVISIONING"

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                with state.lock: state.status = "IDLE"
                self._respond(400, '{"error": "Invalid JSON"}')
                return

            vms = data.get('vms', [])
            if not vms:
                with state.lock: state.status = "IDLE"
                self._respond(400, '{"error": "No VMs provided"}')
                return

            become_password = data.get('become_password') or None
            if not become_password:
                with state.lock: state.status = "IDLE"
                self._respond(400, '{"error": "become_password es obligatorio"}')
                return

            log.info(f"Peticion de aprovisionamiento manual para {len(vms)} VMs. Lanzando en background...")

            def run_provision_wrapper():
                try:
                    provision_all_nodes(vms, become_password=become_password)
                finally:
                    with state.lock:
                        if state.status == "ANSIBLE_PROVISIONING":
                            state.status = "IDLE"
                            log.info("Aprovisionamiento manual finalizado. Estado restaurado a IDLE.")

            threading.Thread(target=run_provision_wrapper, daemon=True).start()
            self._respond(200, json.dumps({"status": "ok", "message": "Aprovisionamiento iniciado en segundo plano"}))
            return



        self._respond(404, '{"error": "not found"}')

def reset_coordinator():
    """
    Reinicia el estado del coordinador a IDLE vaciando todas las colas.
    Además, mata cualquier proceso de Ansible que pudiera estar corriendo en background.
    """
    import subprocess
    log.warning("Reseteando coordinador. Matando procesos de Ansible huérfanos si los hay...")
    # Matamos ansible sin que salte error si no existe el proceso
    subprocess.run(["pkill", "-f", "ansible-playbook"], check=False)
    subprocess.run(["pkill", "-f", "ssh.*ansible"], check=False)

    with state.lock:
        prev_status = state.status
        state.pending_nodes = []
        state.in_progress_nodes = []
        state.completed_nodes = []
        state.status = "IDLE"
    log.info(f"Coordinador reseteado a IDLE (estado anterior: {prev_status}).")

def start_batch_deployment(vms):
    """
    Recibe una lista de VMs desde el CLI.
    Si la cola está inactiva, la inicializa.
    Si está instalando por PXE, añade a la cola dinámicamente evitando duplicados.
    Si está en fase final (Ansible), rechaza la petición.
    """
    to_start = []
    
    with state.lock:
        if state.status == "ANSIBLE_PROVISIONING":
            return False, "La maqueta ya está en la fase final de configuración de Ansible. Espera a que termine para añadir más máquinas."
            
        new_nodes = [n for n in vms if n.get('name') != 'jumpstart']
        added_count = 0
        
        if state.status == "IDLE":
            state.pending_nodes = new_nodes
            state.in_progress_nodes = []
            state.completed_nodes = []
            state.status = "PXE_INSTALLING"
            
            # Extraer el primer bloque
            to_start = state.pending_nodes[:state.batch_size]
            state.pending_nodes = state.pending_nodes[state.batch_size:]
            state.in_progress_nodes.extend(to_start)
            added_count = len(new_nodes)
        else:
            # state.status es PXE_INSTALLING, añadimos de forma inteligente a la cola
            for node in new_nodes:
                name = node.get('name')
                in_pending = any(n.get('name') == name for n in state.pending_nodes)
                in_progress = any(n.get('name') == name for n in state.in_progress_nodes)
                
                if not in_pending and not in_progress:
                    # Sacamos de completados por si el usuario está forzando una reinstalación
                    state.completed_nodes = [n for n in state.completed_nodes if n.get('name') != name]
                    state.pending_nodes.append(node)
                    added_count += 1
            
            # Si hay "huecos" en la ventana deslizante, aprovechamos para rellenarlos al instante
            while len(state.in_progress_nodes) < state.batch_size and state.pending_nodes:
                next_node = state.pending_nodes.pop(0)
                state.in_progress_nodes.append(next_node)
                to_start.append(next_node)
                
    # Las llamadas de red a la Host API siempre fuera del lock de memoria
    if to_start:
        log.info(f"{CYAN}[BAREMETAL]{NC} Iniciando despliegue PXE. Capacidad de ventana: {YELLOW}{state.batch_size}{NC} nodos.")
        names = [n.get('name') for n in to_start]
        log.info(f"{CYAN}[BAREMETAL]{NC} Cola total: {YELLOW}{len(state.pending_nodes) + len(to_start)}{NC}. Lote inicial a procesar: {YELLOW}{names}{NC}")
        log.info(f"{CYAN}[BAREMETAL]{NC} Solicitando a la API del Host la creación de {YELLOW}{len(to_start)}{NC} VMs: {names}")
        create_vms(to_start, host_api_global)
        
    return True, f"Añadidos {added_count} nodos a la cola de despliegue."

def process_node_ready(node_name):
    """
    Lógica de la Ventana Deslizante desencadenada por un callback.
    """
    to_start = None
    all_done = False

    with state.lock:
        if state.status != "PXE_INSTALLING":
            log.warning(f"{YELLOW}[BAREMETAL] Se recibió callback para {node_name} pero el estado global es {state.status}.{NC}")
            return
            
        node = next((n for n in state.in_progress_nodes if n.get('name') == node_name), None)
        if not node:
            log.warning(f"{YELLOW}[BAREMETAL] Nodo {node_name} no encontrado en in_progress_nodes (¿Evento duplicado o cancelado?).{NC}")
            return
            
        # 1. Desplazar nodo (solo modificamos memoria, sin I/O)
        state.in_progress_nodes.remove(node)
        state.completed_nodes.append(node)
        
        in_prog_names = [n.get('name') for n in state.in_progress_nodes]
        log.info(f"{CYAN}[BAREMETAL]{NC} ---> ¡Nodo '{GREEN}{node_name}{NC}' completado! Instalación Ubuntu finalizada.")
        log.info(f"{CYAN}[BAREMETAL]{NC} Hueco liberado. Nodos instalándose ahora: {in_prog_names if in_prog_names else 'Ninguno'}")
        
        # 2. Avanzar ventana
        if state.pending_nodes:
            next_node = state.pending_nodes.pop(0)
            state.in_progress_nodes.append(next_node)
            log.info(f"{CYAN}[BAREMETAL]{NC} <--- Despachando siguiente nodo de la cola: '{GREEN}{next_node.get('name')}{NC}'")
            log.info(f"{CYAN}[BAREMETAL]{NC} Progreso global: {GREEN}{len(state.completed_nodes)}{NC} completados | {YELLOW}{len(state.in_progress_nodes)}{NC} instalando | {BLUE}{len(state.pending_nodes)}{NC} pendientes.")
            to_start = next_node
        else:
            if len(state.in_progress_nodes) == 0:
                all_done = True
                state.status = "ANSIBLE_PROVISIONING"

    # Llamadas de red SIEMPRE fuera del lock
    if to_start:
        log.info(f"{CYAN}[BAREMETAL]{NC} Solicitando a la API del Host la creación de VM: '{GREEN}{to_start.get('name')}{NC}'")
        create_vms([to_start], host_api_global)
        
    if all_done:
        log.info(f"{CYAN}[BAREMETAL]{NC} {GREEN}=============================================================={NC}")
        log.info(f"{CYAN}[BAREMETAL]{NC} Fase de instalación PXE finalizada ({GREEN}{len(state.completed_nodes)}{NC} nodos completados).")
        log.info(f"{CYAN}[BAREMETAL]{NC} Solicitando parcheo de specs finales (recursos y boot order) a la API...")
        
        # Usamos una copia de los nodos para no retener la referencia mutable
        nodes_to_provision = list(state.completed_nodes)

        # Aplicar boot order y recursos de producción a todas las VMs de golpe.
        # Esta llamada es síncrona y en paralelo: espera a que cada VM se apague
        # y aplica los cambios. Si alguna falla, lo sabemos antes de lanzar Ansible.
        specs_ok = apply_post_install_specs(host_api_global, nodes_to_provision)
        if not specs_ok:
            log.error(f"{RED}[BAREMETAL] Alguna VM no pudo ser reconfigurada correctamente. Revisa los logs del vbox-api.{NC}")
            log.error(f"{RED}Se intentará lanzar Ansible de todas formas, pero algunas VMs pueden arrancar por red.{NC}")
        
        log.info(f"{CYAN}[BAREMETAL]{NC} Encendiendo la maqueta con hardware definitivo para la fase de software...")
        start_virtualbox_vms(nodes_to_provision, host_api_global, vm_type="headless")
        
        log.info(f"{MAGENTA}[ANSIBLE]{NC} {MAGENTA}=============================================================={NC}")
        log.info(f"{MAGENTA}[ANSIBLE]{NC} Entregando el control a Ansible. Iniciando aprovisionamiento...")
        with state.lock:
            become_password = state.become_password
        provision_all_nodes(nodes_to_provision, become_password=become_password)
        
        # Al terminar todo el bloque de Ansible (que puede tardar minutos), reiniciamos el estado
        with state.lock:
            state.status = "IDLE"
            state.completed_nodes = []
            log.info("Despliegue global finalizado. Orquestador vuelve a estado IDLE.")

def run_callback_server(nodes, host_api_url, port=8081, batch_size=3):
    global host_api_global
    host_api_global = host_api_url
    state.batch_size = batch_size
    log.info(f"=== Servidor Coordinador iniciando en puerto {port} (Batch Size: {batch_size}) ===")
    server = http.server.HTTPServer(('0.0.0.0', port), CoordinatorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == '__main__':
    # Redirigir logs a stdout para que systemd los capture en journalctl
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s — %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stdout
    )

    from provisioning.jumpstart.parsers import load_all_nodes, load_settings_file

    nodes_dir = os.path.join(REPO_DIR, 'config', 'nodes')
    settings_path = os.path.join(REPO_DIR, 'config', 'settings.yml')

    nodes = load_all_nodes(nodes_dir)
    if not nodes:
        print('[-] Error: No se encontraron definiciones de nodos YAML.')
        sys.exit(1)

    settings = load_settings_file(settings_path)

    host_api_ip   = settings.get('host_api', {}).get('ip', '192.168.56.1')
    host_api_port = settings.get('host_api', {}).get('port', 7070)
    host_api_url  = f'http://{host_api_ip}:{host_api_port}'

    port       = settings.get('orchestrator', {}).get('port', 8081)
    batch_size = settings.get('orchestrator', {}).get('batch_size', 3)

    run_callback_server(nodes, host_api_url, port=port, batch_size=batch_size)
