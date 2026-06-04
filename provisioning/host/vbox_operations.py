#!/usr/bin/env python3
"""
vbox_operations.py — Operaciones de alto nivel sobre VMs de VirtualBox.

Cada función encapsula una operación completa (crear, borrar, arrancar, etc.)
y puede ser invocada desde el servidor HTTP o desde tests/CLI.
Todas las operaciones masivas delegan en _run_parallel(), que gestiona el
ThreadPoolExecutor de forma uniforme para cualquier número de VMs.
"""
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from provisioning.host.vbox_helpers import (
    get_existing_vms,
    is_vm_powered_off,
    start_vm,
    control_vm,
    unregister_vm,
    create_vm_base,
    modify_vm,
    add_sata_controller,
    create_medium,
    attach_disk,
    sanitize_vm_name,
    get_default_machine_folder
)

log = logging.getLogger("vbox-api")

# Máximo de VMs procesadas en paralelo (VBoxSVC tolera bien hasta ~8)
_MAX_WORKERS = 8

# Valores por defecto para creación de VMs
DEFAULT_CPUS = 1
DEFAULT_RAM_MB = 1024
DEFAULT_DISK_GB = 20
DEFAULT_VRAM = 16
DEFAULT_OSTYPE = "Ubuntu_64"
DEFAULT_GRAPHICS = "vmsvga"


# ── Utilidad interna ──────────────────────────────────────────────────────────

def _run_parallel(fn, items):
    """
    Ejecuta fn(item) para cada item de la lista y devuelve los resultados.

    - 0 items → [] sin trabajo.
    - 1 item  → llamada directa, sin overhead de hilos.
    - N items → ThreadPoolExecutor con min(N, _MAX_WORKERS) workers.

    El orden de los resultados no está garantizado (depende de which future
    completes first), lo que es correcto para operaciones independientes.
    """
    if not items:
        return []
    if len(items) == 1:
        return [fn(items[0])]
    with ThreadPoolExecutor(max_workers=min(len(items), _MAX_WORKERS)) as executor:
        futures = [executor.submit(fn, item) for item in items]
        return [f.result() for f in as_completed(futures)]


# ── modifyvm (boot order + specs) ─────────────────────────────────────────────

def _modifyvm_one(spec, timeout_s=180):
    """
    Espera a que una VM esté apagada y aplica los cambios (boot order, RAM, CPUs).

    Parámetros
    ----------
    spec : dict
        Claves: "vm" (str), "boot" (list, opt), "ram_mb" (int, opt), "cpus" (int, opt).
    timeout_s : int
        Segundos máximos de espera a que la VM se apague (por defecto 3 min).

    Devuelve
    --------
    (vm_name: str, ok: bool, msg: str)
    """
    vm_name = spec["vm"]

    log.info("[%s] Esperando apagado para aplicar modifyvm...", vm_name)
    for _ in range(timeout_s // 2):
        if is_vm_powered_off(vm_name):
            ok, out = modify_vm(
                vm_name,
                boot=spec.get("boot"),
                ram_mb=spec.get("ram_mb"),
                cpus=spec.get("cpus")
            )
            if ok:
                log.info("[%s] modifyvm aplicado correctamente.", vm_name)
                return vm_name, True, "Configuración aplicada correctamente."
            log.error("[%s] Error en modifyvm: %s", vm_name, out)
            return vm_name, False, f"Error en modifyvm: {out}"
        time.sleep(2)

    msg = f"Timeout: '{vm_name}' no se apagó en {timeout_s}s."
    log.error(msg)
    return vm_name, False, msg


def apply_specs_bulk(nodes_specs):
    """Aplica boot order y recursos a múltiples VMs en paralelo."""
    successes, failures = [], []
    for vm_name, ok, msg in _run_parallel(_modifyvm_one, nodes_specs):
        if ok:
            successes.append(vm_name)
        else:
            failures.append(f"{vm_name}: {msg}")
    return successes, failures


# ── Arranque / Parada ─────────────────────────────────────────────────────────

def start_vms(vms, vm_type="headless"):
    """Arranca VMs en paralelo. Devuelve lista de errores (vacía si todo OK)."""
    def _start(vm_name):
        ok, out = start_vm(vm_name, vm_type)
        return None if ok else f"{vm_name}: {out.strip()}"
    return [e for e in _run_parallel(_start, vms) if e]


def stop_vms(vms, mode="acpipowerbutton"):
    """Detiene VMs en paralelo. Devuelve lista de errores (vacía si todo OK)."""
    def _stop(vm_name):
        ok, out = control_vm(vm_name, mode)
        return None if ok else f"{vm_name}: {out.strip()}"
    return [e for e in _run_parallel(_stop, vms) if e]


# ── Creación masiva ───────────────────────────────────────────────────────────

def create_vms(vms, vm_dir=None):
    """
    Crea, configura y arranca varias VMs en paralelo.
    Si una VM ya existe, la elimina antes de recrearla.
    """
    if vm_dir is None:
        vm_dir = get_default_machine_folder() or os.path.expanduser("~/VirtualBox VMs")
    else:
        vm_dir = os.path.expanduser(vm_dir)
    existing_vms = get_existing_vms()

    def _create_one(vm):
        name = vm.get("name")
        if not name:
            return [], None

        msgs = []

        # Eliminar si ya existía
        if name in existing_vms:
            control_vm(name, "poweroff")
            unregister_vm(name, delete=True)
            msgs.append(f"Eliminada VM previa '{name}'")

        disk_gb = vm.get("disk_gb", DEFAULT_DISK_GB)
        ostype  = vm.get("ostype", DEFAULT_OSTYPE)

        # 1. Registrar VM
        ok, err = create_vm_base(name, ostype)
        if not ok:
            return msgs, f"Error creando VM '{name}': {err}"

        # 2. Configurar hardware y redes
        modify_vm(
            name,
            cpus=vm.get("cpus", DEFAULT_CPUS),
            ram_mb=vm.get("ram_mb", DEFAULT_RAM_MB),
            boot=["net", "disk", "none", "none"],
            vram=vm.get("vram", DEFAULT_VRAM),
            graphicscontroller=vm.get("graphicscontroller", DEFAULT_GRAPHICS),
            networks=vm.get("networks", [])
        )

        # 3. Controlador SATA + disco virtual
        add_sata_controller(name)
        
        disk_path = os.path.join(vm_dir, sanitize_vm_name(name), f"{sanitize_vm_name(name)}.vdi")
        os.makedirs(os.path.dirname(disk_path), exist_ok=True)
        
        if create_medium(disk_path, disk_gb * 1024)[0]:
            attach_disk(name, disk_path)

        # 4. Arrancar
        start_vm(name, "headless")
        msgs.append(f"Desplegada y encendida VM '{name}'")
        return msgs, None

    log_msgs, errors = [], []
    for vm_msgs, err in _run_parallel(_create_one, vms):
        log_msgs.extend(vm_msgs)
        if err:
            errors.append(err)
    return log_msgs, errors


# ── Borrado masivo ────────────────────────────────────────────────────────────

def delete_vms(vms):
    """
    Apaga y elimina varias VMs en paralelo.
    Devuelve list[str] con un mensaje de resultado por VM.
    """
    existing_vms = get_existing_vms()
    names = [vm.get("name") for vm in vms
             if vm.get("name") and vm.get("name") in existing_vms]

    def _delete_one(name):
        control_vm(name, "poweroff")
        for _ in range(5):  # reintentar para evitar VBOX_E_INVALID_OBJECT_STATE
            if unregister_vm(name, delete=True)[0]:
                return f"VM '{name}' eliminada"
            time.sleep(1)
        return f"VM '{name}': timeout al borrar (lock no liberado)"

    return _run_parallel(_delete_one, names)
