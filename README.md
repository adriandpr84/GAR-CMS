# 🚀 Orquestador de Infraestructura Baremetal (GAR)

Bienvenidos al repositorio del proyecto de **Gestión y Administración de Redes (GAR)**. 

Este proyecto implementa una solución de **aprovisionamiento baremetal automatizado** 100% orientada a datos (YAML-driven) que permite desplegar, configurar e instalar un clúster de máquinas virtuales en VirtualBox de forma totalmente desatendida.

---

## 📖 Documentación Oficial

Hemos estructurado la documentación para cumplir de manera rigurosa con los requisitos del proyecto. Por favor, revisa los documentos en orden:

1. ⚙️ **[01. Datos de Configuración](docs/01_datos_configuracion.md)**: Explicación de los datos de entrada (ficheros YAML) requeridos para definir redes y la parametrización hardware de cada nodo.
2. 🗺️ **[02. Diagrama y Rutas](docs/02_diagrama_y_rutas.md)**: Diagrama de la topología de red (`main` e `internal`) y reglas de enrutamiento aplicadas en el nodo Jumpstart durante el despliegue y producción.
3. 🚀 **[03. Manual de Administración](docs/03_manual_administracion.md)**: Procedimientos operativos estándar. Incluye los pasos de despliegue automatizado, y cómo escalar frontales web, base de datos y puestos *hot-desk*.
4. 📋 **[04. Software Baseline](docs/04_software_baseline.md)**: Inventario detallado con las versiones exactas de SO, hipervisor y dependencias del orquestador.

---

## 📂 Árbol de Directorios

La estructura del proyecto está diseñada para ser completamente escalable:

```text
GAR-pruebas/
├── docs/                          # 📘 Documentación oficial del proyecto
│   ├── 01_datos_configuracion.md
│   ├── 02_diagrama_y_rutas.md
│   ├── 03_manual_administracion.md
│   └── 04_software_baseline.md
├── config/                        # ⚙️ Definiciones YAML orientadas a datos
│   ├── networks.yml               # Parametrización de subredes (main, internal)
│   ├── settings.yml               # Configuración global y puertos de API
│   └── nodes/                     # Directorio con los YAML de cada máquina
├── ansible/                       # ⚙️ Gestión de Configuración (Fase 2)
│   └── playbooks/                 # Playbooks de Ansible
├── provisioning/                  # 📦 Aprovisionamiento de VMs vacías (Fase 1)
│   ├── jumpstart/                 # Código que se ejecuta en la VM base
│   ├── scripts/                   # Scripts auxiliares (bootstrap_jumpstart.sh)
│   ├── services/                  # Servicios systemd (vbox-api, config-manager)
│   ├── templates/                 # Plantillas Jinja2 (PXE, DHCP, Cloud-Init)
│   ├── host/                      # Scripts para ejecutar en el Host Anfitrión
│   │   └── vbox_api_server.py     # Demonio de la API de VirtualBox

├── cms-deployer                 # 🚀 CLI principal de aprovisionamiento
├── AGENTS.md                      # Reglas estrictas de arquitectura
└── README.md                      # Este portal de inicio
```

---

## ⚡ Inicio Rápido (Quick-Start)

Si ya has leído el [Manual de Administración](docs/03_manual_administracion.md), estos son los comandos de uso diario:

### En el Host Anfitrión (Tu PC)
```bash
# Iniciar la API de VirtualBox (requiere Python 3)
python3 provisioning/host/vbox_api_server.py
```

### En el Servidor Jumpstart (Desde dentro de la VM)
```bash
# Generar configuraciones PXE/DHCP (Requiere privilegios para reiniciar servicios)
sudo ./cms-deployer generate-configs

# Desplegar la maqueta completa (crea VMs vacías e inicia el PXE Boot)
./cms-deployer deploy

# Destruir toda la maqueta y liberar disco (CUIDADO)
./cms-deployer undeploy
```
