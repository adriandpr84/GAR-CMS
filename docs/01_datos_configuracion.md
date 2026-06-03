# Datos de Entrada para el Despliegue

La infraestructura se define íntegramente mediante ficheros YAML (Data-Driven). Esto permite configurar todos los datos de entrada sin modificar el código fuente.

## 1. Configuración Global (`config/settings.yml`)

Este fichero centraliza las variables de entorno, credenciales y puertos de la infraestructura.

```yaml
# IP y puerto donde escucha la API REST en el Host (para VBoxManage)
host_api:
  ip: "192.168.56.1"
  port: 7070

# Parámetros del nodo aprovisionador
jumpstart:
  callback_port: 8081
  ssh_user: "admin"

# Valores por defecto para todas las VMs
defaults:
  vm_user: "admin"
  vm_password: "secreto_por_defecto"
```

## 2. Redes (`config/networks.yml`)

Define los prefijos de red, pasarelas y servidores DNS.

```yaml
networks:
  - name: intnet_main
    subnet: "192.168.1.0"
    netmask: "255.255.255.0"
    gateway: "192.168.1.254"
    dns:
      - "8.8.8.8"
      - "1.1.1.1"

  - name: intnet_internal
    subnet: "192.168.2.0"
    netmask: "255.255.255.0"
    gateway: "192.168.2.254"
    dns:
      - "8.8.8.8"
```

## 3. Definición de Nodos (`config/nodes/*.yml`)

Cada nodo se define en un fichero individual. Para solventar los altos requisitos de hardware de los instaladores modernos (Ubuntu Subiquity requiere ~7GB de RAM), el orquestador permite separar los recursos temporales de aprovisionamiento de los recursos finales de producción.

```yaml
name: web-frontend-1
type: web-server
mac: "08:00:27:00:01:01"

auth:
  username: admin
  password: "$6$HASH_GENERADO" # El orquestador generará el hash automáticamente si se provee en texto plano

networks:
  - name: intnet_main
    type: intnet
    ip: "192.168.1.101"

# Recursos temporales asignados durante la fase de instalación PXE (Fase 1)
provisioning:
  cpus: 2
  ram_mb: 7168

# Recursos definitivos de producción aplicados tras el primer reinicio
vbox_specs:
  cpus: 1
  ram_mb: 1024
  disk_gb: 20
```
