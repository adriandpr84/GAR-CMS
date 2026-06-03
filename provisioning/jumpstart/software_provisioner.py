import os
import socket
import time
import subprocess

CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
NC = '\033[0m'

def wait_for_ssh(node_ip, name, max_wait=600):
    """Espera hasta que el puerto 22 (SSH) del nodo esté disponible."""
    print(f"[{CYAN}*{NC}] Esperando a que '{name}' ({node_ip}) responda por SSH...", flush=True)
    elapsed = 0
    while elapsed < max_wait:
        try:
            with socket.create_connection((node_ip, 22), timeout=3):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass
        time.sleep(5)
        elapsed += 5
        
    print(f"[{RED}!{NC}] Timeout ({max_wait}s) esperando SSH de '{name}'.", flush=True)
    return False

def run_ansible_site(become_password=None):
    """Ejecuta el playbook principal (site.yml)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(script_dir))
    inventory_path = os.path.join(repo_root, 'ansible', 'inventory', 'hosts.yml')
    playbook_path = os.path.join(repo_root, 'ansible', 'playbooks', 'site.yml')
    
    print(f"[{GREEN}+{NC}] Nodos listos. Lanzando Playbook Maestro...", flush=True)
    print(f"[{CYAN}>{NC}] Ejecutando: ansible-playbook -i {inventory_path} {playbook_path}", flush=True)
    
    ansible_dir = os.path.join(repo_root, 'ansible')
    env = os.environ.copy()
    env['ANSIBLE_ROLES_PATH'] = os.path.join(ansible_dir, 'roles')
    env['ANSIBLE_FORCE_COLOR'] = '1'
    env['PY_COLORS'] = '1'
    env['ANSIBLE_HOST_KEY_CHECKING'] = 'false'
    
    if become_password:
        # Inyectamos la contraseña como variable de entorno: no requiere TTY interactivo
        env['ANSIBLE_BECOME_PASSWORD'] = become_password
    
    cmd = [
        'ansible-playbook', '-i', inventory_path, playbook_path,
        '--ssh-extra-args', '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
    ]
    
    result = subprocess.run(
        cmd,
        text=True,
        cwd=ansible_dir,
        env=env
    )
    if result.returncode == 0:
        print(f"[{GREEN}+{NC}] Nodos provisionados con éxito.", flush=True)
        return True
    else:
        print(f"[{RED}!{NC}] El despliegue de Ansible terminó con errores (código {result.returncode}).", flush=True)
        return False

def provision_all_nodes(nodes_list, become_password=None):
    """
    Comprueba SSH en todos los nodos y lanza la ejecución.
    """
    print(f"[{CYAN}*{NC}] Fase final (Ansible): Verificando {len(nodes_list)} nodos antes del despliegue...", flush=True)
    
    all_ready = True
    for node in nodes_list:
        name = node.get('name')
        node_networks = node.get('networks', [])
        node_ip = node_networks[0].get('ip') if node_networks else None

        if not node_ip:
            print(f"[{YELLOW}!{NC}] IP no encontrada para {name}. Saltando comprobación.", flush=True)
            continue

        if not wait_for_ssh(node_ip, name):
            all_ready = False
            
    if all_ready:
        run_ansible_site(become_password=become_password)
    else:
        print(f"[{RED}!{NC}] Abortando ejecución de Ansible porque algunos nodos no están listos.", flush=True)

