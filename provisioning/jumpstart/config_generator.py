import os
import subprocess
import jinja2
from provisioning.jumpstart.parsers import load_networks_file, load_settings_file

GREEN = '\033[92m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
RED = '\033[91m'
NC = '\033[0m'
import yaml

def _generate_ansible_inventory(nodes, repo_root):
    """Genera dinámicamente el archivo hosts.yml de Ansible basado en los nodos YAML."""
    print(f"[{CYAN}*{NC}] Generando inventario dinámico de Ansible...")
    
    inventory = {
        'all': {
            'vars': {
                'ansible_user': 'admin',
                'ansible_ssh_private_key_file': '/home/admin/.ssh/id_rsa'
            },
            'children': {}
        }
    }
    
    children = inventory['all']['children']
    
    for node in nodes:
        name = node.get('name')
        if name == 'jumpstart':
            continue
            
        node_type = node.get('type')
        if not node_type:
            continue
            
        networks = node.get('networks', [])
        if not networks:
            continue
            
        ip = networks[0].get('ip')
        if not ip:
            continue
            
        if node_type not in children:
            children[node_type] = {'hosts': {}}
            
        children[node_type]['hosts'][name] = {'ansible_host': ip}
        
    inventory_path = os.path.join(repo_root, 'ansible', 'inventory', 'hosts.yml')
    os.makedirs(os.path.dirname(inventory_path), exist_ok=True)
    
    try:
        with open(inventory_path, 'w') as f:
            yaml.dump(inventory, f, default_flow_style=False, sort_keys=False)
        print(f"[{GREEN}+{NC}] Inventario Ansible generado exitosamente en {inventory_path}")
    except Exception as e:
        print(f"[{RED}-{NC}] Error generando inventario Ansible: {e}")

def get_jumpstart_pubkey(ssh_user='admin'):
    """Lee la clave pública SSH del jumpstart. Busca en el home de admin y root."""
    key_paths = [
        f"/home/{ssh_user}/.ssh/id_rsa.pub",
        "/root/.ssh/id_rsa.pub",
        os.path.expanduser("~/.ssh/id_rsa.pub")
    ]
    for path in key_paths:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read().strip()

    print(f"[{RED}-{NC}] Error: No se encontró ninguna clave pública SSH.")
    print(f"    Genera una con:  ssh-keygen -t rsa -b 2048 -f /home/{ssh_user}/.ssh/id_rsa -N \"\"")
    print(f"    O ejecuta el playbook de Ansible del jumpstart para generarla automáticamente.")
    raise SystemExit(1)



def _get_jinja_env(templates_dir):
    """Inicializa y devuelve el entorno de Jinja2."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_dir),
        trim_blocks=True,
        lstrip_blocks=True
    )

def _generate_dhcp_config(nodes, networks_list, dhcp_config_path, jinja_env):
    """Genera el fichero de configuración de DHCP. Devuelve True si cambió, False si no."""
    print(f"[{CYAN}*{NC}] Generando archivo DHCP global...")
    
    try:
        template = jinja_env.get_template('dhcpd.conf.j2')
        dhcp_content = template.render(nodes=nodes, networks=networks_list)
        
        # Comprobar si ya existe y si su contenido es idéntico
        if os.path.exists(dhcp_config_path):
            with open(dhcp_config_path, 'r') as f:
                current_content = f.read()
            if current_content == dhcp_content:
                print(f"[{GREEN}✓{NC}] El archivo DHCP no ha cambiado. Se omite la escritura.")
                return False
                
        with open(dhcp_config_path, 'w') as f:
            f.write(dhcp_content)
        print(f"[{GREEN}+{NC}] Archivo DHCP actualizado en {dhcp_config_path}")
        return True
    except Exception as e:
        print(f"[{RED}-{NC}] Error generando DHCP: {e}")
        return False

def _generate_pxe_menu(node, jumpstart_ip, tftp_pxe_dir, jinja_env):
    """Genera el archivo de menú PXELINUX específico para la MAC de un nodo."""
    mac = node.get('mac')
    mac_formatted = "01-" + mac.lower().replace(':', '-')
    pxe_file_path = os.path.join(tftp_pxe_dir, mac_formatted)
    
    try:
        template = jinja_env.get_template('pxe_menu.j2')
        pxe_menu_content = template.render(node=node, jumpstart_ip=jumpstart_ip)
        with open(pxe_file_path, 'w') as f:
            f.write(pxe_menu_content)
    except Exception as e:
        print(f"[{RED}-{NC}] Error generando menú PXE para {node.get('name')}: {e}")

def _generate_autoinstall_files(node, jumpstart_ip, ssh_key, templates_dir, web_autoinstall_dir, networks_list, jinja_env, settings):
    """Genera los archivos meta-data y user-data inyectando variables en las plantillas."""
    name = node.get('name')
    
    node_install_dir = os.path.join(web_autoinstall_dir, name)
    os.makedirs(node_install_dir, exist_ok=True)
    
    # meta-data
    meta_data_src = os.path.join(templates_dir, "meta-data")
    meta_data_dst = os.path.join(node_install_dir, "meta-data")
    if os.path.exists(meta_data_src):
        with open(meta_data_src, 'r') as src, open(meta_data_dst, 'w') as dst:
            dst.write(src.read())
    else:
        with open(meta_data_dst, 'w') as dst:
            dst.write("instance-id: nocloud-vm\n")
            
    # Configuración de usuario y password
    auth_config = node.get('auth', {})
    defaults = settings.get('defaults', {})
    
    vm_user = auth_config.get('username', defaults.get('vm_user', 'admin'))
    vm_password_hash = auth_config.get('password', defaults.get('vm_password', ''))

    if not vm_password_hash:
        print(f"[{RED}-{NC}] Error: No se encontró contraseña para el nodo '{node.get('name')}'. Define 'password' (en formato hash $6$) en el YAML del nodo o en settings.yml.")
        raise SystemExit(1)

    if not vm_password_hash.startswith('$'):
        print(f"[{RED}-{NC}] Error: La contraseña del nodo '{node.get('name')}' no está hasheada.")
        print(f"    Para Ubuntu Autoinstall es OBLIGATORIO usar un hash (ej. $6$...).")
        print(f"    Genera un hash válido con: openssl passwd -6 tu_contraseña")
        raise SystemExit(1)

    callback_port = settings.get('jumpstart', {}).get('callback_port', 8081)


    # user-data (Jinja2)
    try:
        template = jinja_env.get_template('user-data.j2')
        user_data_content = template.render(
            node=node,
            networks=networks_list,
            ssh_pub_key=ssh_key,
            jumpstart_ip=jumpstart_ip,
            vm_user=vm_user,
            vm_password_hash=vm_password_hash,
            callback_port=callback_port
        )
        user_data_dst = os.path.join(node_install_dir, "user-data")
        with open(user_data_dst, 'w') as f:
            f.write(user_data_content)
    except Exception as e:
        print(f"[{RED}-{NC}] Error generando user-data para {name}: {e}")

def generate_pxe_configs(nodes, templates_dir=None):
    """Punto de entrada principal. Coordina la generación de todas las configuraciones."""
    print("[*] Iniciando generación de configuraciones de red y aprovisionamiento...")
    
    provisioning_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.dirname(provisioning_dir)
    
    if templates_dir is None:
        templates_dir = os.path.join(provisioning_dir, "templates")
        
    settings = load_settings_file(os.path.join(repo_root, "config", "settings.yml"))
    jumpstart_user = settings.get('jumpstart', {}).get('ssh_user', 'admin')
    
    ssh_key = get_jumpstart_pubkey(jumpstart_user)
    networks_list = load_networks_file(os.path.join(repo_root, "config", "networks.yml"))
    
    dhcp_config_path = "/etc/dhcp/dhcpd.conf"
    tftp_pxe_dir = "/srv/tftp/pxelinux.cfg"
    web_autoinstall_dir = "/var/www/html/autoinstall"
    
    os.makedirs(os.path.dirname(dhcp_config_path), exist_ok=True)
    os.makedirs(tftp_pxe_dir, exist_ok=True)
    os.makedirs(web_autoinstall_dir, exist_ok=True)
    
    # Configurar entorno Jinja2
    jinja_env = _get_jinja_env(templates_dir)
    
    # 1. Generar DHCP global
    dhcp_changed = _generate_dhcp_config(nodes, networks_list, dhcp_config_path, jinja_env)
    
    # 2. Generar ficheros por nodo
    processed_nodes = 0
    for node in nodes:
        name = node.get('name')
        mac = node.get('mac')
        
        if name == 'jumpstart' or not mac or not node.get('networks'):
            continue
            
        # Determinar IP del jumpstart (Gateway de la red primaria del nodo)
        primary_net_name = node['networks'][0].get('name')
        jumpstart_ip = next((n.get('gateway') for n in networks_list if n.get('name') == primary_net_name), None)
        
        if not jumpstart_ip:
            print(f"[{RED}-{NC}] Error: No se pudo determinar la IP del jumpstart para la red {primary_net_name}.")
            continue
            
        _generate_pxe_menu(node, jumpstart_ip, tftp_pxe_dir, jinja_env)
        _generate_autoinstall_files(node, jumpstart_ip, ssh_key, templates_dir, web_autoinstall_dir, networks_list, jinja_env, settings)
        processed_nodes += 1
        
    if processed_nodes > 0:
        print(f"[{GREEN}+{NC}] Generados menús PXE y plantillas Cloud-Init para {processed_nodes} nodos.")

    # 3. Generar inventario de Ansible
    _generate_ansible_inventory(nodes, repo_root)

    # 4. Reiniciar servicios si es necesario
    if dhcp_changed:
        print(f"[{CYAN}*{NC}] Se detectaron cambios en el DHCP. Reiniciando isc-dhcp-server...")
        try:
            subprocess.run(["systemctl", "restart", "isc-dhcp-server"], check=True)
            print(f"[{GREEN}+{NC}] Servicio DHCP actualizado y activo.")
        except subprocess.CalledProcessError as e:
            print(f"[{YELLOW}!{NC}] Advertencia: Hubo un problema reiniciando isc-dhcp-server ({e}). ¿Tienes permisos de sudo?")
    else:
        print(f"[{GREEN}✓{NC}] Configuración DHCP sin cambios. No es necesario reiniciar isc-dhcp-server.")
        
    print(f"[{GREEN}✓{NC}] Los servicios TFTP y HTTP no requieren reinicio (leen los archivos en caliente).")
    print(f"[{GREEN}✓{NC}] Generación de configuraciones finalizada exitosamente.")
