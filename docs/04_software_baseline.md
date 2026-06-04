# Software Baseline

Lista de todos los componentes software que forman parte de la solución de aprovisionamiento, sus versiones exactas y dependencias.

## Sistema Base y Virtualización

| Software | Versión | Propósito | URL Origen |
| :--- | :--- | :--- | :--- |
| **Ubuntu Server** | 22.04.5 LTS (Jammy Jellyfish) | Sistema Operativo base de todas las máquinas virtuales. | [Descarga ISO](https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso) |
| **VirtualBox** | 7.0.x | Hipervisor Host. | [VirtualBox](https://www.virtualbox.org/) |
| **Python** | 3.10+ | Lenguaje del orquestador (`cms-deployer` y coordinador). | Incluido en Ubuntu 22.04 |

## Dependencias de Infraestructura (Jumpstart)

| Software | Versión | Propósito | Instalación |
| :--- | :--- | :--- | :--- |
| **Ansible** | Core (Última estable APT) | Motor de aprovisionamiento y configuración del Jumpstart. | `apt-get install ansible` |
| **ISC DHCP Server** | Última estable APT | Servidor DHCP para las redes internas. | `apt-get install isc-dhcp-server` |
| **TFTP-HPA** | Última estable APT | Servidor TFTP para proveer los binarios de arranque PXE. | `apt-get install tftpd-hpa` |
| **Apache2** | Última estable APT | Servidor HTTP para servir ficheros Cloud-Init y la ISO. | `apt-get install apache2` |
| **Syslinux / Pxelinux** | Última estable APT | Bootloader de red. | `apt-get install pxelinux syslinux-common` |
| **Iptables-persistent**| Última estable APT | Persistencia de reglas NAT y enrutamiento. | `apt-get install iptables-persistent` |

## Módulos Python (Orquestador)

No se requieren librerías externas de `pip`. Todas son instaladas a nivel de sistema mediante repositorios oficiales:
- `python3-yaml`
- `python3-jinja2`

## Componentes de la Infraestructura en los Nodos (Desplegados por Ansible)

| Componente | Versión / Imagen | Nodos donde se ejecuta | Propósito | Origen / Instalación |
| :--- | :--- | :--- | :--- | :--- |
| **Nginx** | 1.18.0 (APT) | `load-balancer`, `web-frontend-1/2` | Balanceador de carga y servidor HTTP frontal. | Repositorio oficial Ubuntu 22.04 |
| **PHP-FPM** | 8.1 (APT) | `web-frontend-1/2` | Procesamiento del código del CMS PHP. | Repositorio oficial Ubuntu 22.04 |
| **WordPress** | 6.x (Latest stable tar.gz) | `web-frontend-1/2` | Aplicación CMS de WordPress. | [WordPress.org](https://wordpress.org/latest.tar.gz) |
| **GlusterFS Server** | 9.x / 10.x (APT) | `storage-node` | Servidor de archivos distribuidos. | Repositorio oficial Ubuntu 22.04 |
| **GlusterFS Client** | 9.x / 10.x (APT) | `web-frontend-1/2` | Cliente para montar el volumen GlusterFS. | Repositorio oficial Ubuntu 22.04 |
| **Docker Engine** | 24.x+ / `docker.io` (APT)| `cluster-node` (master/worker), `monitoring` | Entorno de ejecución de contenedores. | Repositorio oficial Ubuntu 22.04 |
| **MariaDB Galera** | `mariadb:10.6` (Docker) | `cluster-master-1/2`, `cluster-worker-1` | Clúster multi-maestro síncrono para base de datos. | Docker Hub / Construido localmente |
| **HAProxy** | `haproxy:2.9` (Docker) | Clúster Swarm (puerto 3306) | Balanceo activo/pasivo del clúster de base de datos. | Docker Hub |
| **CheckMK Raw** | `checkmk/check-mk-raw:2.3.0-latest` | `monitoring` (Docker) | Motor centralizado de monitorización de infraestructura. | Docker Hub |
| **CheckMK Agent** | 2.3.0p47 (DEB) | Todos los nodos (excepto `monitoring`) | Agente nativo para recolección de métricas y procesos. | Descargado del servidor CheckMK local |
| **UFW** | 0.36+ (APT) | Todos los nodos de la maqueta | Cortafuegos local para bloqueo de puertos. | Repositorio oficial Ubuntu 22.04 |


