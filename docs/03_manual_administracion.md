# Manual de Administración

Este manual describe los procedimientos operativos estándar para la gestión inicial de la infraestructura CMS de la empresa Fake Enterprise (Fase de Aprovisionamiento Automático de Nodos Baremetal y Gestión de Servicios en Producción).

## 1. Pasos necesarios para llevar a cabo un despliegue

El despliegue está completamente automatizado, pero requiere un entorno inicial (el nodo Jumpstart) desde el cual se orquestará el resto de la red.

### Fase A: Preparación del Entorno (Jumpstart)
1. Instalar manualmente el nodo Jumpstart con Ubuntu Server 22.04 LTS conectada a dos adaptadores de red (NAT e Internal Network).
2. Clonar el repositorio oficial del proyecto dentro del Jumpstart.
3. Iniciar el demonio de la API REST en el Host físico:
   ```bash
   python3 provisioning/host/vbox_api_server.py
   ```
4. Ejecutar el script de aprovisionamiento inicial con privilegios de administrador en el Jumpstart:
   ```bash
   sudo ./scripts/bootstrap_jumpstart.sh
   ```
   *Nota: Este script instalará y configurará de manera automática los servicios DHCP, TFTP y el Servidor Web (HTTP) necesarios para las instalaciones desatendidas por red.*

### Fase B: Despliegue de la Infraestructura
1. Configurar los ficheros de datos de entrada (YAML) en la ruta `config/nodes/` definiendo los recursos y redes de cada máquina.
2. Como usuario sin privilegios, lanzar el comando de despliegue principal del orquestador:
   ```bash
   ./cms-deployer deploy
   ```
3. **Flujo Automático:**
   - El orquestador generará las configuraciones dinámicas de PXE/DHCP.
   - Solicitará la creación y encendido de las nuevas máquinas al hipervisor Host a través de la API REST.
   - Las máquinas arrancarán por red (PXE), descargarán el sistema base de Ubuntu y se autoinstalarán.
   - Al terminar, se notifica automáticamente al Jumpstart, quien cambia el orden de arranque de las VMs a disco duro, ajusta la memoria RAM a los valores de producción y enciende la máquina virtual de manera definitiva.

## 2. Cómo examinar la monitorización de los elementos del despliegue

El sistema de monitorización centralizado se encuentra en el nodo `monitoring` (dentro de la red `internal`, IP `192.168.2.30`) y se basa en **CheckMK Raw Edition** ejecutándose sobre un contenedor Docker.

1. **Servicio SNMP:** Todos los nodos de la infraestructura tienen instalado y activo el agente SNMP (`snmpd`), configurado a través del rol `common` de Ansible. El agente expone estadísticas del sistema en el puerto UDP 161 con la comunidad `comunidad-gar`.
2. **Acceso al Panel de Control (CheckMK):**
   - **Acceso Centralizado y Seguro (Recomendado)**: Desde cualquier navegador (tanto interno como externo), accediendo a través del balanceador de carga en `https://192.168.1.10/monitoring/` (las credenciales por defecto son usuario `cmkadmin` y contraseña `admin-gar-2026`).
   - **Acceso Directo (Red Interna)**: Desde un puesto de la red `main` (como un *hot-desk*), también se puede acceder directamente a la IP del contenedor en `http://192.168.2.30/monitoring/`.
   - El panel muestra automáticamente el estado de salud en tiempo real de todos los nodos y servicios monitorizados gracias al registro y descubrimiento automático mediante la API.
3. **Monitorización de Servicios (Requisito 11):**
   - El fichero `/etc/snmp/snmpd.conf` en cada nodo tiene configuradas extensiones de proceso (`proc nginx`, `proc dockerd`, `proc glusterd`, `proc mysqld`).
   - CheckMK sondea periódicamente estas métricas SNMP, permitiendo visualizar de manera directa si los servicios críticos están activos en los frontales web, en el clúster de base de datos o en los servidores de almacenamiento.

## 3. Pasos necesarios para ampliar los puestos hot-desk

La red `main` soporta la adición de nuevos puestos hot-desk de forma sencilla gracias al diseño data-driven del orquestador.

1. **Crear archivo de configuración del nodo:**
   Crear un nuevo fichero en `config/nodes/hotdesks/hotdesk-9.yml` con la parametrización de red y hardware. Ejemplo:
   ```yaml
   name: hotdesk-9
   type: hotdesk
   mac: "08:00:27:00:01:09" # Sustituir por una MAC libre
   networks:
     - name: intnet_main
       ip: "192.168.1.108"
   ```
2. **Actualizar el inventario de Ansible:**
   Editar `ansible/inventory/hosts.yml` y añadir el nuevo host bajo el grupo `hotdesk`:
   ```yaml
       hotdesk:
         hosts:
           ...
           hotdesk-9:
             ansible_host: 192.168.1.108
   ```
3. **Regenerar configuraciones PXE/DHCP en el Jumpstart:**
   ```bash
   sudo ./cms-deployer generate-configs
   ```
4. **Lanzar el despliegue del nuevo nodo:**
   ```bash
   ./cms-deployer deploy hotdesk-9
   ```
   *El orquestador creará de forma automática la VM en el Host con los recursos mínimos, iniciará la instalación por red y, al terminar, la reconfigurará con las especificaciones de producción y ejecutará el playbook de aprovisionamiento de software.*

## 4. Pasos necesarios para sustituir/aumentar frontales web

La arquitectura web cuenta con balanceo de carga redundante de Nginx. Añadir o sustituir un frontal web se puede realizar de forma dinámica sin interrumpir el servicio.

1. **Definir el nuevo nodo frontal:**
   Crear un fichero YAML en `config/nodes/infra/web-frontend-3.yml`:
   ```yaml
   name: web-frontend-3
   type: web-frontend
   mac: "08:00:27:00:01:0D"
   networks:
     - name: intnet_main
       ip: "192.168.1.13"
   ```
2. **Actualizar el inventario de Ansible:**
   Añadir el host `web-frontend-3` al grupo `web-frontend` en `ansible/inventory/hosts.yml`:
   ```yaml
       web-frontend:
         hosts:
           ...
           web-frontend-3:
             ansible_host: 192.168.1.13
   ```
3. **Desplegar el nuevo nodo:**
   ```bash
   ./cms-deployer deploy web-frontend-3
   ```
4. **Comportamiento del aprovisionamiento:**
   - Durante la ejecución del playbook, Ansible configurará `web-frontend-3` como cliente de GlusterFS.
   - El volumen compartido `gv0` del `storage-node` se montará en `/var/www/cms_shared`, haciendo que el código de WordPress esté sincronizado inmediatamente sin necesidad de copiar archivos.
   - Ansible actualizará la configuración de Nginx en el nodo `load-balancer` (ya que el archivo de configuración se renderiza iterando sobre el grupo `web-frontend` del inventario), agregando el nuevo servidor al pool del balanceador y recargando el servicio de forma transparente.

## 5. Pasos necesarios para sustituir/aumentar los nodos de la base de datos

La base de datos SQL (MariaDB Galera) se ejecuta en un clúster de alta disponibilidad sobre Docker Swarm en la red `internal`.

### Para sustituir un nodo existente:
1. **Marcar nodo como inactivo en Swarm:**
   En el manager principal (`cluster-master-1`), drenar las tareas del nodo a sustituir para asegurar que no ejecuta contenedores activos:
   ```bash
   docker node update --availability drain <nombre_nodo_caido>
   ```
2. **Desplegar el nuevo nodo físico:**
   Crear la nueva VM con el orquestador (usando el mismo nombre o uno nuevo) definiendo sus especificaciones en `config/nodes/cluster/`.
3. **Asociar el nodo al Swarm:**
   Al lanzar `./cms-deployer deploy <nuevo_nodo>`, Ansible lo unirá automáticamente al Swarm en la fase de provisionamiento de software.
4. **Fijar la base de datos al nuevo host (si aplica):**
   Si se requiere que la réplica de Galera corra en el nuevo host, edita `ansible/roles/cluster-node/defaults/main.yml` actualizando la variable `db_node_X` correspondiente, y redespliega la stack desde el manager:
   ```bash
   docker stack deploy -c /opt/gar/swarm/mariadb-galera-stack.yml gar_db
   ```
   *El nuevo nodo iniciará un contenedor de MariaDB Galera que se conectará automáticamente a los otros miembros del clúster (`db1`/`db2`/`db3`) e iniciará una transferencia de estado (SST/IST) para sincronizar los datos sin pérdida de servicio.*



