# Acceso a los servidores de despliegue

## Hipervisor (Host VirtualBox)
- Comando de acceso: `ssh tbworkers5` (acceso directo por claves SSH configuradas en `~/.ssh/config`)
- Contraseña sudo: `pass123` (el usuario es `demo`, pero se usa ssh con keys)

## Jumpstart (Nodo orquestador)
- Comando de acceso: Desde `tbworkers5`, ejecutar `ssh jumpstart` (acceso por claves SSH)
- Contraseña sudo: `admin` (el usuario es `admin`)

## Notas:
- El Jumpstart se encarga de ejecutar el servidor coordinador (`provisioning-coordinator`).
- El hipervisor (`tbworkers5`) ejecuta la API de VirtualBox que acepta peticiones REST para gestionar las VMs.
