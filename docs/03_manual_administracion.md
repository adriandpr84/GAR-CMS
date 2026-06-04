# Manual de Administración

Este manual describe los procedimientos operativos estándar para la gestión inicial de la infraestructura CMS de la empresa Fake Enterprise (Fase de Aprovisionamiento Automático de Nodos Baremetal y Gestión de Servicios en Producción).

## 1. Pasos necesarios para llevar a cabo un despliegue

El despliegue está completamente automatizado, pero requiere un entorno inicial (el nodo Jumpstart) desde el cual se orquestará el resto de la red.

### Fase A: Preparación del Entorno (Jumpstart)
1. Instalar manualmente el nodo Jumpstart con Ubuntu Server 22.04 LTS conectada a dos adaptadores de red (NAT e Internal Network).
2. Clonar el repositorio oficial del proyecto dentro del Jumpstart.
3. Iniciar el demonio de la API REST en el Host físico:
   ```bash
   ./provisioning/host/vbox-api-helper.sh start
   ```
4. Ejecutar el script de aprovisionamiento inicial con privilegios de administrador en el Jumpstart:
   ```bash
   sudo ./provisioning/jumpstart/bootstrap_jumpstart.sh
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
   - Al terminar, se notifica automáticamente al Jumpstart, quien cambia el orden de arranque de las VMs a disco duro, ajusta la memoria RAM a los valores de producción y enciende la máquina virtual de manera definitiva para servir los playbooks de Ansible.

*Nota: Para conocer en profundidad todas las opciones y parámetros del orquestador, consulte la [Referencia del CLI](cms-deployer-cli.md).*

## 2. Cómo examinar la monitorización de los elementos del despliegue

El sistema de monitorización centralizado se encuentra en el nodo `monitoring` (dentro de la red `internal`, IP `192.168.2.30`) y se basa en **CheckMK Raw Edition** ejecutándose sobre un contenedor Docker.

1. **Agente CheckMK:** Todos los nodos de la infraestructura tienen instalado y activo el agente nativo de CheckMK (`check-mk-agent`), configurado a través del rol `checkmk-agent` de Ansible. El agente expone estadísticas del sistema de forma segura a través de un socket en el puerto TCP 6556.
2. **Acceso al Panel de Control (CheckMK):**
   - **Acceso Centralizado y Seguro (Recomendado)**: Desde cualquier navegador (tanto interno como externo), accediendo a través del balanceador de carga en `https://192.168.1.10/monitoring/` (las credenciales por defecto son usuario `cmkadmin` y contraseña `admin-gar-2026`).
   - El panel muestra automáticamente el estado de salud en tiempo real de todos los nodos y servicios monitorizados gracias al registro y descubrimiento automático mediante la API.
3. **Monitorización de Servicios (Requisito 11):**
   - El agente nativo de CheckMK reporta automáticamente el estado de los procesos del sistema operativo.
   - El servidor CheckMK está configurado para realizar descubrimientos automáticos de servicios críticos, permitiendo supervisar si los procesos clave (`nginx`, `dockerd`, `glusterd`, `mysqld`, `php-fpm`) están levantados y operativos.


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
2. **Regenerar configuraciones PXE/DHCP en el Jumpstart:**
   ```bash
   sudo ./cms-deployer generate-configs
   ```
3. **Lanzar el despliegue del nuevo nodo:**
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
2. **Desplegar el nuevo nodo:**
   ```bash
   ./cms-deployer deploy web-frontend-3
   ```
3. **Comportamiento del aprovisionamiento:**
   - Durante la ejecución del playbook, Ansible configurará `web-frontend-3` como cliente de GlusterFS.
   - El volumen compartido `gv0` del `storage-node` se montará en `/var/www/cms_shared`, haciendo que el código de WordPress esté sincronizado inmediatamente sin necesidad de copiar archivos.
   - Ansible actualizará la configuración de Nginx en el nodo `load-balancer` (ya que el archivo de configuración se renderiza iterando sobre el grupo `web-frontend` del inventario), agregando el nuevo servidor al pool del balanceador y recargando el servicio de forma transparente.

## 5. Pasos necesarios para sustituir/aumentar los nodos de la base de datos

La base de datos SQL (MariaDB Galera) se ejecuta en un clúster de alta disponibilidad sobre Docker Swarm en la red `internal`. El despliegue de las réplicas es completamente dinámico y se genera sobre todos los nodos del grupo `[cluster-node]` del inventario de Ansible, a excepción de aquellos que tengan configurado explícitamente `is_db: false` en sus ficheros YAML individuales.

Gracias a la arquitectura Data-Driven del proyecto:
* **El archivo `ansible/inventory/hosts.yml` se genera de forma completamente automática** antes de cada despliegue. El orquestador `cms-deployer` lee los ficheros de configuración de `config/nodes/` y detecta qué VMs existen en VirtualBox para reconstruir el inventario sobre la marcha.
* **No es necesario acceder por SSH a ningún nodo del clúster** para realizar tareas administrativas como el drenado, borrado de nodos o el despliegue del stack de base de datos.

---

### Para sustituir un nodo de base de datos de Swarm (ej. `cluster-worker-1` por uno nuevo `cluster-worker-3`):

1. **Eliminar el nodo antiguo:**
   * Apaga y elimina la máquina virtual `cluster-worker-1` de VirtualBox.
   ```bash
   ./cms-deployer undeploy cluster-worker-1
   ```
   * Elimina su fichero de configuración en `config/nodes/cluster/cluster-worker-1.yml`.
2. **Definir el nuevo nodo:**
   * Crea el fichero de configuración de la nueva máquina en `config/nodes/cluster/cluster-worker-3.yml` asignándole sus parámetros de red y el tipo `cluster-node`.
3. **Ejecutar el despliegue:**
   Lanza el comando del orquestador en la máquina Jumpstart indicando el nuevo nodo:
   ```bash
   ./cms-deployer deploy cluster-worker-3
   ```
   **Acción automática del sistema (Transparente para el usuario):**
   * El orquestador creará la nueva VM y generará las configuraciones de red (DHCP, PXE y Cloud-Init).
   * **Regenerará automáticamente el archivo `hosts.yml`**, eliminando a `cluster-worker-1`, incorporando a `cluster-worker-3` y pasando las variables personalizadas (como `is_db: false`).
   * La VM se autoinstalará por red y, una vez listo el SSH, el orquestador invocará a Ansible de manera global.
   * Ansible detectará que `cluster-worker-1` ya no está en el inventario y **lo expulsará/drenará de Swarm de forma automática**.
   * Unirá `cluster-worker-3` al Swarm, le aplicará la etiqueta de base de datos y **redesplegará el stack de base de datos y HAProxy en caliente**, autosincronizándose la nueva réplica.

---

### Para aumentar (escalar) el número de nodos de base de datos (ej. de 3 a 5 nodos):

1. **Definir los nuevos nodos físicos:**
   Crea los ficheros de configuración YAML correspondientes en la ruta `config/nodes/cluster/` (ej. `cluster-worker-3.yml`, `cluster-worker-4.yml`).
2. **Ejecutar el despliegue para los nuevos nodos:**
   Lanza el comando de despliegue indicando las nuevas máquinas:
   ```bash
   ./cms-deployer deploy cluster-worker-3
   ./cms-deployer deploy cluster-worker-4
   ```
   **Acción automática del sistema:**
   * El orquestador registrará las nuevas VMs, las instalará por PXE, y **regenerará automáticamente el inventario `hosts.yml`** incluyendo a todos los nodos activos.
   * Al ejecutarse Ansible, aprovisionará los nuevos nodos e incrementará dinámicamente el tamaño de la base de datos de 3 a 5 instancias.
   * Actualizará la configuración del balanceador HAProxy y redesplegará el stack en Swarm sin caída del servicio, iniciando la sincronización de las nuevas réplicas (`db4`, `db5`).

## 6. Procedimiento para pruebas de carga y simulación de tráfico (TrafficMix)

Se incluye una herramienta desarrollada en Python que simulan usuarios concurrentes accediendo a diferentes páginas del CMS (WordPress), forzando lecturas en caliente de la base de datos MariaDB Galera.

Las pruebas se ejecutan de las siguientes maneras:

### A. Simulación desde fuera de la red (Host físico)
Desde la consola del ordenador anfitrión, se puede lanzar el TrafficMix apuntando al balanceador a través de su IP de la red Host-Only (`192.168.56.11`):
```bash
# Simular 5 usuarios concurrentes durante 60 segundos.
python3 trafficmix.py https://192.168.56.11 60 5
```

### B. Simulación desde un puesto de trabajo (Hot-desk)
Para simular el tráfico interno generado por un empleado:
1. Conéctate a un puesto hot-desk (ej. `hotdesk-1`):
   ```bash
   ssh hotdesk-1
   ```
2. Ejecuta el script de simulación (Python) apuntando a la IP de la red `main` del balanceador (`192.168.1.10`):
   ```bash
   python3 trafficmix.py http://192.168.1.10 45 3
   ```

### C. Verificación y validación de la actividad
Mientras la simulación está en curso, se puede comprobar el impacto y la distribución de carga:
* Accediendo al panel de **CheckMK** en `https://192.168.56.11/monitoring/` para visualizar los picos de CPU, accesos de red y carga en los frontales web (`web-frontend-1/2`) y nodos de base de datos.
