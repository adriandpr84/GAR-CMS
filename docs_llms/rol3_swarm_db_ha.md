# Rol 3 — Clustering & Database HA

## 1. Objetivo

Este rol configura los cuatro nodos del grupo `cluster` para crear un clúster Docker Swarm y desplegar una base de datos SQL en alta disponibilidad mediante MariaDB Galera.

Nodos usados:

| Nodo | IP | Función |
|---|---:|---|
| cluster-master-1 | 192.168.2.10 | Manager principal de Swarm y nodo Galera db1 |
| cluster-master-2 | 192.168.2.11 | Manager secundario de Swarm y nodo Galera db2 |
| cluster-worker-1 | 192.168.2.12 | Worker de Swarm y nodo Galera db3 |
| cluster-worker-2 | 192.168.2.13 | Worker de Swarm disponible para failover/servicios adicionales |

## 2. Qué instala el rol

El rol `ansible/roles/swarm` realiza estas acciones:

1. Instala Docker en los cuatro nodos.
2. Habilita y arranca el servicio Docker.
3. Crea el clúster Docker Swarm.
4. Inicializa `cluster-master-1` como manager principal.
5. Une `cluster-master-2` como manager secundario.
6. Une `cluster-worker-1` y `cluster-worker-2` como workers.
7. Etiqueta los nodos que alojarán la base de datos.
8. Construye una imagen local `gar/mariadb-galera:1.0` en cada nodo y despliega un stack llamado `gar_db` con MariaDB Galera y HAProxy.

## 3. Archivos creados/modificados

```text
ansible/inventory/hosts.yml
ansible/roles/swarm/defaults/main.yml
ansible/roles/swarm/handlers/main.yml
ansible/roles/swarm/tasks/main.yml
ansible/roles/swarm/tasks/docker.yml
ansible/roles/swarm/tasks/swarm.yml
ansible/roles/swarm/tasks/database.yml
ansible/roles/swarm/tasks/verify.yml
ansible/roles/swarm/templates/mariadb-galera-stack.yml.j2
ansible/roles/swarm/templates/haproxy.cfg.j2
ansible/roles/swarm/templates/Dockerfile.mariadb-galera.j2
ansible/roles/swarm/templates/docker-entrypoint-galera.sh.j2
config/deploy_lists/rol3.txt
docs/rol3_swarm_db_ha.md
scripts/check-rol3.sh
```

## 4. Ejecución del rol

Desde la raíz del repositorio, en la máquina Jumpstart:

```bash
sudo ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/site.yml --tags swarm
```

Si se quiere comprobar antes la conectividad:

```bash
ansible -i ansible/inventory/hosts.yml cluster -m ping
```

## 5. Comprobaciones principales

### Comprobar Docker en todos los nodos

```bash
ansible -i ansible/inventory/hosts.yml cluster -m shell -a "docker --version" -b
```

### Comprobar el clúster Swarm

Desde `cluster-master-1`:

```bash
docker node ls
```

Resultado esperado aproximado:

```text
cluster-master-1   Ready   Active   Leader
cluster-master-2   Ready   Active   Reachable
cluster-worker-1   Ready   Active
cluster-worker-2   Ready   Active
```

### Comprobar servicios desplegados

```bash
docker service ls
```

Deben aparecer servicios parecidos a:

```text
gar_db_db1
gar_db_db2
gar_db_db3
gar_db_db-lb
```

También se puede comprobar el stack completo:

```bash
docker stack services gar_db
docker stack ps gar_db
```

## 6. Prueba SQL básica

Desde `cluster-master-1`:

```bash
mysql -h 127.0.0.1 -P 3306 -u cmsuser -p'CmsPass2026!' -e "SHOW DATABASES;"
```

La base de datos de la práctica se llama:

```text
cmsdb
```

Usuario de aplicación:

```text
cmsuser
```

Contraseña de laboratorio:

```text
CmsPass2026!
```

## 7. Prueba de alta disponibilidad

Primero se mira dónde están los servicios:

```bash
docker stack ps gar_db
```

Después se apaga uno de los nodos con base de datos, por ejemplo `cluster-worker-1`:

```bash
sudo poweroff
```

O desde el host VirtualBox:

```bash
VBoxManage controlvm cluster-worker-1 poweroff
```

Después, desde `cluster-master-1`:

```bash
docker node ls
docker service ls
docker stack ps gar_db
```

Lo que se debe observar:

- El clúster Swarm sigue activo.
- Los managers siguen manteniendo el estado del clúster.
- HAProxy mantiene el puerto SQL publicado.
- MariaDB Galera conserva nodos activos mientras exista quórum suficiente.

## 8. Añadir un nuevo nodo al Swarm

En el manager principal:

```bash
docker swarm join-token worker
```

En el nuevo nodo se ejecuta el comando que devuelva Docker, parecido a:

```bash
docker swarm join --token TOKEN 192.168.2.10:2377
```

Luego se comprueba desde el manager:

```bash
docker node ls
```

## 9. Sustituir un nodo de base de datos

Pasos generales:

1. Eliminar o apagar el nodo dañado.
2. Arrancar el nuevo nodo con la misma red interna.
3. Instalar Docker con el rol de Ansible.
4. Unirlo al Swarm con el token correspondiente.
5. Etiquetarlo como nodo de base de datos:

```bash
docker node update --label-add gar.role=database --label-add gar.db=true NUEVO_NODO
```

6. Actualizar las variables `db_node_1`, `db_node_2` o `db_node_3` si cambia el nombre del nodo.
7. Relanzar el rol:

```bash
sudo ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/site.yml --tags swarm
```

## 10. Script de comprobación

Se incluye un script para revisar la entrega:

```bash
./scripts/check-rol3.sh
```

También permite indicar inventario:

```bash
./scripts/check-rol3.sh ansible/inventory/hosts.yml
```

## 11. Explicación para la defensa

El rol instala Docker en los cuatro nodos asignados y crea un clúster Docker Swarm. `cluster-master-1` se usa como manager principal, `cluster-master-2` como segundo manager y los dos workers se unen como nodos de ejecución. Sobre ese Swarm se construye una imagen local de MariaDB Galera y se despliega un stack de base de datos con tres servicios Galera, cada uno fijado a un nodo distinto, y un HAProxy que publica el puerto 3306. De esta forma, la capa de datos queda replicada y se puede comprobar con `docker node ls`, `docker service ls`, `docker stack ps gar_db` y una conexión SQL básica.

