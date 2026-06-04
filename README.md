# 🏛️ Infraestructura de Alta Disponibilidad y Seguridad para Fake Enterprise (GAR)

Este repositorio contiene la solución completa de diseño, despliegue y aprovisionamiento automático de la infraestructura de red e IT de **Fake Enterprise**, desarrollada para la asignatura **Gestión y Administración de Redes (GAR)**.

La solución integra tecnologías de alta disponibilidad, almacenamiento distribuido y observabilidad, garantizando que el carácter sensible de los datos del CMS esté protegido mediante un modelo estricto de seguridad perimetral y firewalls locales.

---

## 🛠️ Resumen de la Solución de Infraestructura

De acuerdo con los requisitos corporativos del enunciado, la infraestructura lógica desplegada consta de:
* **Segmentación de Red:** División estricta en dos subredes: `main` (red externa y puestos de trabajo) e `internal` (servicios internos y datos aislados de internet).
* **Clúster de Base de Datos HA:** 3 nodos MariaDB Galera síncronos y balanceo activo/pasivo con HAProxy sobre un clúster Docker Swarm (2 maestros, 2 workers) en la red `internal`.
* **Capa Web CMS:** 2 servidores web frontales con Nginx + PHP-FPM sirviendo WordPress, integrados en un almacenamiento distribuido compartido con **GlusterFS**.
* **Balanceo de Carga Perimetral:** Un proxy reverso Nginx en la red `main` que actúa como único punto de entrada externo HTTP/S.
* **Observabilidad Centralizada:** Un servidor **CheckMK Raw Edition** en la red `internal` que monitoriza todos los recursos del sistema y los servicios mediante el agente nativo de CheckMK.

* **Seguridad y Aislamiento:** Firewalls locales (**UFW**) restrictivos por nodo y redirección del enrutamiento de red de producción a través del balanceador/router.
* **Aprovisionamiento Automático:** Orquestación desatendida desde un nodo **Jumpstart** mediante instalación por red (PXE, DHCP, TFTP, Apache y Cloud-Init) y aprovisionamiento final con **Ansible**.

---

## 📖 Documentación Oficial

La documentación detallada se encuentra estructurada para cumplir de manera rigurosa con los requisitos del proyecto. Por favor, revisa los documentos en orden:

1. ⚙️ **[01. Datos de Configuración](docs/01_datos_configuracion.md)**: Explicación de los datos de entrada (ficheros YAML) requeridos para definir redes y la parametrización de cada nodo.
2. 🗺️ **[02. Diagrama y Rutas](docs/02_diagrama_y_rutas.md)**: Diagrama de la topología de red (`main` e `internal`) y reglas de enrutamiento aplicadas en el nodo Jumpstart durante el despliegue y producción.
3. 🚀 **[03. Manual de Administración](docs/03_manual_administracion.md)**: Procedimientos operativos estándar. Incluye los pasos de despliegue automatizado, y cómo escalar frontales web, base de datos y puestos *hot-desk*.
4. 📋 **[04. Software Baseline](docs/04_software_baseline.md)**: Inventario detallado con las versiones exactas de SO, hipervisor y dependencias del software.

---

## 📂 Estructura de Directorios

La estructura del repositorio está organizada para separar claramente la definición de la maqueta, las configuraciones de red y los playbooks de automatización:

```text
gar/
├── docs/                          # 📘 Documentación oficial del proyecto (Checklist de la solución)
│   ├── 01_datos_configuracion.md
│   ├── 02_diagrama_y_rutas.md
│   ├── 03_manual_administracion.md
│   └── 04_software_baseline.md
├── config/                        # ⚙️ Definiciones YAML orientadas a datos (Data-Driven)
│   ├── networks.yml               # Parámetros globales de subredes (main, internal)
│   ├── settings.yml               # Configuración global, credenciales y puertos
│   └── nodes/                     # Declaración YAML de especificaciones de cada VM
├── ansible/                       # ⚙️ Gestión de Configuración y Despliegue de Servicios
│   ├── playbooks/                 # Playbook principal de ejecución (site.yml)
│   ├── inventory/                 # Inventarios de Ansible (hosts.yml generado dinámicamente)
│   └── roles/                     # Roles reutilizables (common, load-balancer, cluster-node, etc.)
├── provisioning/                  # 📦 Aprovisionamiento automático e instalación PXE
│   ├── jumpstart/                 # Código Python de orquestación y scripts auxiliares (bootstrap)
│   ├── templates/                 # Plantillas Jinja2 para PXE, DHCP y autoinstalación (Cloud-Init)
│   └── host/                      # API del Host para automatizar VirtualBox y scripts del host
├── trafficmix.py                  # 🚦 Generador de tráfico concurrente y pruebas de carga (Req 15)
├── cms-deployer                   # 🚀 CLI principal de control de despliegue
└── README.md                      # Este portal de inicio
```

---

## ⚡ Inicio Rápido (Quick-Start)

Para llevar a cabo el despliegue automático, sigue estas instrucciones rápidas:

### 1. En el Host Anfitrión (Tu PC físico)
Inicia la API del Host que comunica el orquestador con el hipervisor VirtualBox:
```bash
python3 provisioning/host/vbox_api_server.py
```

### 2. En la VM Jumpstart (Nodo de aprovisionamiento)
Realiza el bootstrap de los servicios y lanza el despliegue completo de la infraestructura de Fake Enterprise:
```bash
# Iniciar servicios de red (DHCP, TFTP, HTTP) en el Jumpstart
sudo ./provisioning/jumpstart/bootstrap_jumpstart.sh

# Desplegar la maqueta completa en VirtualBox (instalación desatendida por red)
./cms-deployer deploy
```
*Una vez finalizado el aprovisionamiento, puedes apagar la VM Jumpstart de forma segura; la infraestructura completa continuará operando y enrutando de forma aislada a través del Load Balancer.*
