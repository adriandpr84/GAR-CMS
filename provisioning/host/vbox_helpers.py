#!/usr/bin/env python3
"""
vbox_helpers.py — Utilidades de bajo nivel para invocar VBoxManage.

Wrapper sobre subprocess para ejecutar comandos VBoxManage y exponer
las primitivas de VirtualBox como funciones puras de Python.
"""
import subprocess
import logging

log = logging.getLogger("vbox-api")


# ── Core (Privado) ────────────────────────────────────────────────────────────

def _vbox(*args):
    """Ejecuta un comando VBoxManage. Devuelve (ok: bool, output: str)."""
    cmd = ["VBoxManage"] + list(args)
    log.info("Ejecutando: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.warning("VBoxManage error: %s", result.stderr.strip())
        return False, result.stderr.strip()
    return True, result.stdout.strip()


def sanitize_vm_name(name):
    """Elimina caracteres peligrosos de un nombre de VM."""
    forbidden = set('"\';&|`$\\/\<>')
    return "".join(c for c in name if c not in forbidden)


# ── Consultas de estado ───────────────────────────────────────────────────────

def parse_vms_output(raw):
    """Extrae nombres de VM de la salida de VBoxManage."""
    vms = []
    for line in raw.splitlines():
        if '"' in line:
            try:
                vms.append(line.split('"')[1])
            except IndexError:
                pass
    return vms


def get_existing_vms():
    """Devuelve la lista de nombres de VMs actualmente registradas."""
    ok, out = _vbox("list", "vms")
    return parse_vms_output(out) if ok else []


def get_vm_state(name):
    """Devuelve el estado de una VM (ej. 'poweroff', 'running') o None."""
    ok, out = _vbox("showvminfo", sanitize_vm_name(name), "--machinereadable")
    if ok:
        for line in out.splitlines():
            if line.startswith('VMState='):
                return line.split('=')[1].strip('"')
    return None


def is_vm_powered_off(name):
    """Comprueba de forma segura si la VM está apagada."""
    return get_vm_state(name) == "poweroff"


# ── Primitivas de ciclo de vida ───────────────────────────────────────────────

def start_vm(name, vm_type="headless"):
    return _vbox("startvm", sanitize_vm_name(name), "--type", vm_type)


def control_vm(name, mode):
    """mode puede ser 'poweroff', 'acpipowerbutton', etc."""
    return _vbox("controlvm", sanitize_vm_name(name), mode)


def unregister_vm(name, delete=True):
    args = ["unregistervm", sanitize_vm_name(name)]
    if delete:
        args.append("--delete")
    return _vbox(*args)


def create_vm_base(name, ostype="Ubuntu_64"):
    return _vbox("createvm", "--name", sanitize_vm_name(name), "--ostype", ostype, "--register")


def modify_vm(name, cpus=None, ram_mb=None, boot=None, vram=None, graphicscontroller=None, networks=None):
    """Aplica configuraciones traduciendo argumentos Python a flags de VBoxManage."""
    args = []
    if cpus:
        args.extend(["--cpus", str(cpus)])
    if ram_mb:
        args.extend(["--memory", str(ram_mb)])
    if boot:
        boot_padded = (boot + ["none", "none", "none", "none"])[:4]
        for i, b in enumerate(boot_padded, 1):
            args.extend([f"--boot{i}", b])
    if vram:
        args.extend(["--vram", str(vram)])
    if graphicscontroller:
        args.extend(["--graphicscontroller", graphicscontroller])
    if networks:
        for idx, net in enumerate(networks, start=1):
            net_type = net.get("type", "intnet")
            args.extend([f"--nic{idx}", net_type])
            if net_type == "intnet":
                args.extend([f"--intnet{idx}", net.get("name", "")])
            if net.get("mac"):
                mac_clean = net["mac"].replace(":", "").replace("-", "").upper()
                args.extend([f"--macaddress{idx}", mac_clean])

    if not args:
        return True, ""
    return _vbox("modifyvm", sanitize_vm_name(name), *args)


def add_sata_controller(name):
    return _vbox("storagectl", sanitize_vm_name(name),
                 "--name", "SATA Controller", "--add", "sata", "--controller", "IntelAHCI")


def create_medium(disk_path, size_mb):
    return _vbox("createmedium", "disk", "--filename", disk_path, "--size", str(size_mb), "--format", "VDI")


def attach_disk(name, disk_path):
    return _vbox("storageattach", sanitize_vm_name(name),
                 "--storagectl", "SATA Controller",
                 "--port", "0", "--device", "0", "--type", "hdd", "--medium", disk_path)
