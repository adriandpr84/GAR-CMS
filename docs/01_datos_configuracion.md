# Datos de Entrada para el Despliegue

La infraestructura se define íntegramente mediante ficheros YAML (diseño *Data-Driven*). Esto permite parametrizar todos los datos de red, hardware y configuraciones de entrada de manera aislada sin modificar el código fuente de los scripts del orquestador.

---

## 1. Configuración Global (`config/settings.yml`)

Este fichero centraliza los parámetros de conexión para el orquestador local y la API del Host, así como las credenciales y recursos por defecto de las VMs.

```yaml
# IP y puerto de la API REST que corre en el Host (para interactuar con VBoxManage)
host_api:
  ip: "192.168.56.1"
  port: 7070

# Parámetros del orquestador de despliegue local (Coordinador)
orchestrator:
  port: 8081
  ssh_user: "admin"
  batch_size: 1

# Valores por defecto aplicados a todas las VMs si no se especifican a nivel de nodo
defaults:
  vm_user: "admin"
  # Hash de la contraseña de usuario para la instalación desatendida de Ubuntu (Subiquity)
  vm_password: "$6$CylgQV.8wYk/VUlE$UpXhP0y5NrH3ZypUfNvOF2/JEu5rRedFbseqWxsJ/dN0.XjeiK9ho.e78NWOysq/4o19qn1MolUcccrIyCjj5."
  
  # Recursos temporales usados por defecto en la fase de instalación desatendida PXE (Subiquity)
  pxe_specs:
    cpus: 6
    ram_mb: 9216
  
  # Recursos finales por defecto para el entorno de producción
  production_specs:
    cpus: 1
    ram_mb: 1024
    disk_gb: 15
```

---

## 2. Definición de Redes (`config/networks.yml`)

Especifica las subredes de la infraestructura, los gateways iniciales (Jumpstart) y finales (Load Balancer), los DNS y los rangos dinámicos del servidor DHCP.

```yaml
networks:
  - name: intnet_main
    subnet: "192.168.1.0"
    netmask: "255.255.255.0"
    gateway: "192.168.1.254"         # Gateway temporal durante la instalación (Jumpstart)
    final_gateway: "192.168.1.10"     # Gateway de producción definitivo (Load Balancer)
    dns: ["8.8.8.8", "8.8.4.4"]
    dhcp_range:
      start: "192.168.1.150"
      end: "192.168.1.200"

  - name: intnet_internal
    subnet: "192.168.2.0"
    netmask: "255.255.255.0"
    gateway: "192.168.2.254"         # Gateway temporal durante la instalación (Jumpstart)
    final_gateway: "192.168.2.20"     # Gateway de producción definitivo (Load Balancer)
    dns: ["8.8.8.8", "8.8.4.4"]
    dhcp_range:
      start: "192.168.2.150"
      end: "192.168.2.200"
```

---

## 3. Definición de Nodos (`config/nodes/`)

Cada máquina virtual se define individualmente en su propio fichero YAML bajo el directorio `config/nodes/`. Dependiendo de su rol, puede definir una o varias interfaces y recursos específicos.

### Ejemplo A: Nodo estándar (`config/nodes/infra/web-frontend-1.yml`)
Define una sola interfaz en la red `main` y redefine su memoria de producción para ajustarse al servidor web.

```yaml
name: web-frontend-1
type: web-frontend
mac: "08:00:27:00:01:0B"
networks:
  - name: intnet_main
    ip: "192.168.1.11"
production_specs:
  ram_mb: 768
  cpus: 1
```

### Ejemplo B: Balanceador/Router (`config/nodes/infra/load-balancer.yml`)
Este nodo está conectado a múltiples switches virtuales (internos), a la red NAT (para salida a internet) y al adaptador Host-Only para administración, por lo que define una lista compleja de redes.

```yaml
name: load-balancer
type: load-balancer
mac: "08:00:27:00:01:0A"
networks:
  - name: intnet_main
    ip: "192.168.1.10"
    gateway: ""   # La ruta por defecto de producción sale por la interfaz NAT
  - name: NAT
    type: nat
  - name: intnet_internal
    ip: "192.168.2.20"
    gateway: ""
  - name: vboxnet0
    type: hostonly
    ip: "192.168.56.11"
```
