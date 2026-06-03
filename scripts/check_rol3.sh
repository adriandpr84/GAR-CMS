#!/bin/bash
set -euo pipefail

INVENTORY="${1:-ansible/inventory/hosts.yml}"
MANAGER="admin@192.168.2.10"
STACK="gar_db"

printf '\n=== 1) Conectividad Ansible ===\n'
ansible -i "$INVENTORY" cluster -m ping

printf '\n=== 2) Docker instalado en los 4 nodos ===\n'
ansible -i "$INVENTORY" cluster -m shell -a "docker --version" -b

printf '\n=== 3) Estado de Docker Swarm ===\n'
ssh "$MANAGER" "docker node ls"

printf '\n=== 4) Servicios desplegados ===\n'
ssh "$MANAGER" "docker service ls"

printf '\n=== 5) Stack de base de datos ===\n'
ssh "$MANAGER" "docker stack services $STACK && docker stack ps $STACK --no-trunc"

printf '\n=== 6) Prueba SQL básica desde el manager ===\n'
ssh "$MANAGER" "mysql -h 127.0.0.1 -P 3306 -u cmsuser -p'CmsPass2026!' -e 'SHOW DATABASES;' || true"

printf '\nComprobación terminada. Si el último comando falla al principio, espera a que Galera termine de arrancar y repite.\n'

