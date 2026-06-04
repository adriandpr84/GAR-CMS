# Referencia del CLI de cms-deployer

El script `cms-deployer` es el orquestador principal para desplegar, gestionar y aprovisionar las máquinas virtuales. A continuación se detalla su uso y comandos disponibles.

## Uso Básico
```
usage: cms-deployer [-h] {deploy,undeploy,generate-configs,provision,start,stop,abort} ...
```

**Acciones disponibles:**
* `deploy`: Desplegar las VMs en VirtualBox a partir de la maqueta
* `undeploy`: Eliminar las VMs de VirtualBox (excepto jumpstart)
* `generate-configs`: Generar configuraciones PXE, DHCP y Autoinstall
* `provision`: Aprovisionar software (Ansible) en las VMs de forma directa
* `start`: Iniciar las VMs en VirtualBox (excepto jumpstart)
* `stop`: Detener las VMs en VirtualBox (excepto jumpstart)
* `abort`: Abortar procesos en curso en el coordinador

---

## Subcomandos

### `deploy`
```text
usage: cms-deployer deploy [-h] [--nodes-dir NODES_DIR]
                           [--templates-dir TEMPLATES_DIR] [--vm-dir VM_DIR]
                           [-f FICHERO]
                           [node ...]

positional arguments:
  node                  Nombres de los nodos a desplegar (opcional, por defecto todos)

options:
  -h, --help            show this help message and exit
  --nodes-dir NODES_DIR Directorio con archivos YAML de nodos
  --templates-dir TEMPLATES_DIR Directorio con plantillas Autoinstall
  --vm-dir VM_DIR       Ruta base para los discos virtuales en el host
  -f, --file FICHERO    Fichero de texto con los nodos a operar (uno por línea, # para comentarios)
```

### `undeploy`
```text
usage: cms-deployer undeploy [-h] [--nodes-dir NODES_DIR]
                             [--templates-dir TEMPLATES_DIR] [--vm-dir VM_DIR]
                             [-f FICHERO]
                             [node ...]

positional arguments:
  node                  Nombres de los nodos a desinstalar (opcional, por defecto todos)
```

### `provision`
```text
usage: cms-deployer provision [-h] [--nodes-dir NODES_DIR]
                              [--templates-dir TEMPLATES_DIR]
                              [--vm-dir VM_DIR] [-f FICHERO]
                              [node ...]

positional arguments:
  node                  Nombres de los nodos a aprovisionar (opcional, por defecto todos)
```

### `start`
```text
usage: cms-deployer start [-h] [--nodes-dir NODES_DIR]
                          [--templates-dir TEMPLATES_DIR] [--vm-dir VM_DIR]
                          [-f FICHERO] [--type {headless,gui,separate}]
                          [node ...]

positional arguments:
  node                  Nombres de los nodos a iniciar (opcional, por defecto todos)

options:
  --type {headless,gui,separate}  Modo de inicio de la VM (headless, gui, separate)
```

### `stop`
```text
usage: cms-deployer stop [-h] [--nodes-dir NODES_DIR]
                         [--templates-dir TEMPLATES_DIR] [--vm-dir VM_DIR]
                         [-f FICHERO]
                         [--mode {poweroff,acpipowerbutton,savestate,pause,resume}]
                         [node ...]

positional arguments:
  node                  Nombres de los nodos a detener (opcional, por defecto todos)

options:
  --mode {poweroff,acpipowerbutton,savestate,pause,resume}
                        Modo de parada de la VM
```

### `generate-configs`
```text
usage: cms-deployer generate-configs [-h] [--nodes-dir NODES_DIR]
                                     [--templates-dir TEMPLATES_DIR]
                                     [--vm-dir VM_DIR] [-f FICHERO]
```

### `abort`
```text
usage: cms-deployer abort [-h] [--nodes-dir NODES_DIR]
                          [--templates-dir TEMPLATES_DIR] [--vm-dir VM_DIR]
                          [-f FICHERO]
```
