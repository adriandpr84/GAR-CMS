#!/usr/bin/env python3
"""
vbox_api_server.py — REST API para VBoxManage en el Host Anfitrión.
Asignatura: Gestión y Administración de Redes (GAR)

Servidor HTTP (stdlib) que expone endpoints REST para gestionar VMs de
VirtualBox. Debe ejecutarse en el HOST, no en el Jumpstart.
El Jumpstart le envía peticiones HTTP para crear, arrancar o reconfigurar VMs.

Uso:
  python3 provisioning/host/vbox_api_server.py
  python3 provisioning/host/vbox_api_server.py --port 7070 --bind 192.168.56.1

Verificar desde el Jumpstart:
  curl http://192.168.56.1:7070/health

Módulos:
  vbox_helpers.py    — wrapper de bajo nivel sobre VBoxManage (subprocess)
  vbox_operations.py — lógica de negocio: crear, borrar, arrancar, etc.
"""

import os
import http.server
import json
import logging
import argparse
from urllib.parse import urlparse, parse_qs

from provisioning.jumpstart.parsers import load_settings_file
from provisioning.host.vbox_helpers import _vbox, sanitize_vm_name, parse_vms_output
from provisioning.host.vbox_operations import (
    apply_specs_bulk,
    start_vms,
    stop_vms,
    create_vms,
    delete_vms,
)

# ── Configuración ──────────────────────────────────────────────────────────────
_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_settings  = load_settings_file(os.path.join(_base_dir, "config", "settings.yml"))

DEFAULT_PORT = _settings.get("host_api", {}).get("port", 7070)
DEFAULT_BIND = _settings.get("host_api", {}).get("ip", "0.0.0.0")

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("vbox-api")

# Valores válidos para los parámetros de los endpoints
_VALID_BOOT  = {"disk", "net", "dvd", "floppy", "none"}
_VALID_TYPES = {"headless", "gui", "separate"}
_VALID_MODES = {"poweroff", "acpipowerbutton", "savestate", "pause", "resume"}


# ── Manejador HTTP ─────────────────────────────────────────────────────────────

class VBoxAPIHandler(http.server.BaseHTTPRequestHandler):
    """
    Manejador HTTP fino: valida la petición y delega en vbox_operations.
    No contiene lógica de negocio; solo parseo HTTP, validación y respuesta.
    """

    def log_message(self, fmt, *args):
        log.info("%s — %s", self.client_address[0], fmt % args)

    # ── Utilidades de respuesta ────────────────────────────────────────────────

    def _json(self, code, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _ok(self, **kwargs):
        self._json(200, {"status": "ok", **kwargs})

    def _error(self, code, message):
        self._json(code, {"status": "error", "message": message})

    def _handle_vbox_error(self, err):
        """Mapea errores de VBoxManage a códigos HTTP semánticos."""
        if "VBOX_E_OBJECT_NOT_FOUND" in err or "Could not find a registered machine" in err:
            self._error(404, err)
        elif "VBOX_E_INVALID_OBJECT_STATE" in err or "already locked" in err or "already running" in err:
            self._error(409, err)
        else:
            self._error(500, err)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    # ── GET ────────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path   = parsed.path

        # GET /health
        if path == "/health":
            ok, _ = _vbox("--version")
            self._ok(service="vbox-api", vboxmanage_available=ok)

        # GET /vbox/vms
        elif path == "/vbox/vms":
            ok, out = _vbox("list", "vms")
            self._ok(vms=parse_vms_output(out)) if ok else self._error(500, out)

        # GET /vbox/running-vms
        elif path == "/vbox/running-vms":
            ok, out = _vbox("list", "runningvms")
            self._ok(vms=parse_vms_output(out)) if ok else self._error(500, out)

        # GET /vbox/vm-info?vm=<nombre>
        elif path == "/vbox/vm-info":
            vm_name = params.get("vm", [None])[0]
            if not vm_name:
                self._error(400, 'Parámetro "vm" requerido')
                return
            ok, out = _vbox("showvminfo", sanitize_vm_name(vm_name), "--machinereadable")
            if ok:
                info = {}
                for line in out.splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        info[k.strip()] = v.strip().strip('"')
                self._ok(vm=vm_name, info=info)
            else:
                self._handle_vbox_error(out)

        else:
            self._error(404, f"Ruta no encontrada: {path}")

    # ── POST ───────────────────────────────────────────────────────────────────

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self._read_body()
        except (json.JSONDecodeError, ValueError) as e:
            self._error(400, f"JSON inválido en el cuerpo: {e}")
            return

        # POST /vbox/modifyvm
        # Body: {"nodes": [{"vm": "nombre", "boot": ["disk","net","none","none"], "ram_mb": N, "cpus": N}, ...]}
        if path == "/vbox/modifyvm":
            nodes_specs = body.get("nodes", [])
            if not isinstance(nodes_specs, list) or not nodes_specs:
                self._error(400, '"nodes" debe ser una lista no vacía'); return
            for spec in nodes_specs:
                if not spec.get("vm"):
                    self._error(400, 'Cada nodo debe tener campo "vm"'); return
                for b in spec.get("boot", []):
                    if b not in _VALID_BOOT:
                        self._error(400, f'Valor de boot inválido: "{b}". Válidos: {sorted(_VALID_BOOT)}'); return
            successes, failures = apply_specs_bulk(nodes_specs)
            if failures:
                self._error(500, "Fallos al aplicar specs: " + "; ".join(failures))
            else:
                self._ok(message=f"Specs aplicadas a {len(successes)} VMs: {', '.join(successes)}")

        # POST /vbox/start
        # Body: {"vms": ["nombre1", ...], "type": "headless"}
        elif path == "/vbox/start":
            vms     = body.get("vms", [])
            vm_type = body.get("type", "headless")
            if not vms or not isinstance(vms, list):
                self._error(400, 'Campo "vms" requerido (lista)'); return
            if vm_type not in _VALID_TYPES:
                self._error(400, f'Tipo inválido: "{vm_type}". Válidos: {sorted(_VALID_TYPES)}'); return
            errors = start_vms(vms, vm_type)
            if errors:
                self._error(500, "Errores iniciando VMs: " + " | ".join(errors))
            else:
                self._ok(message=f"{len(vms)} VMs iniciadas en modo {vm_type}")

        # POST /vbox/stop
        # Body: {"vms": ["nombre1", ...], "mode": "acpipowerbutton"}
        elif path == "/vbox/stop":
            vms  = body.get("vms", [])
            mode = body.get("mode", "acpipowerbutton")
            if not vms or not isinstance(vms, list):
                self._error(400, 'Campo "vms" requerido (lista)'); return
            if mode not in _VALID_MODES:
                self._error(400, f'Modo inválido: "{mode}". Válidos: {sorted(_VALID_MODES)}'); return
            errors = stop_vms(vms, mode)
            if errors:
                self._error(500, "Errores deteniendo VMs: " + " | ".join(errors))
            else:
                self._ok(message=f"{len(vms)} VMs detenidas ({mode})")

        # POST /vbox/create-vms
        # Body: {"vms": [{...}, ...]}
        elif path == "/vbox/create-vms":
            vms = body.get("vms", [])
            if not isinstance(vms, list):
                self._error(400, '"vms" debe ser una lista'); return
            vm_dir = _settings.get("host_api", {}).get("vm_dir")
            log_msgs, errors = create_vms(vms, vm_dir=vm_dir)
            if errors:
                self._error(500, "Errores creando VMs: " + " | ".join(errors))
            else:
                self._ok(message="Creación masiva completada", details=log_msgs)

        # POST /vbox/delete-vms
        # Body: {"vms": [{"name": "..."}, ...]}
        elif path == "/vbox/delete-vms":
            vms = body.get("vms", [])
            if not isinstance(vms, list):
                self._error(400, '"vms" debe ser una lista'); return
            log_msgs = delete_vms(vms)
            self._ok(message="Borrado masivo completado", details=log_msgs)

        else:
            self._error(404, f"Endpoint no encontrado: {path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VBox API Server — REST API para VBoxManage")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Puerto de escucha (por defecto: {DEFAULT_PORT})")
    parser.add_argument("--bind", default=DEFAULT_BIND,
                        help=f"Dirección IP de escucha (por defecto: {DEFAULT_BIND})")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("  GAR — VBox API Server")
    log.info("  Escuchando en http://%s:%d", args.bind, args.port)
    log.info("=" * 60)
    for endpoint in [
        "GET  /health",
        "GET  /vbox/vms",
        "GET  /vbox/running-vms",
        "GET  /vbox/vm-info?vm=<nombre>",
        'POST /vbox/modifyvm        {"nodes": [{"vm": "...", "boot": ["disk","net"], "ram_mb": N, "cpus": N}]}',
        'POST /vbox/start           {"vms": ["..."], "type": "headless"}',
        'POST /vbox/stop            {"vms": ["..."], "mode": "poweroff"}',
        'POST /vbox/create-vms      {"vms": [...]}',
        'POST /vbox/delete-vms      {"vms": [{"name": "..."}]}',
    ]:
        log.info("  %s", endpoint)
    log.info("=" * 60)

    server = http.server.HTTPServer((args.bind, args.port), VBoxAPIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Servidor detenido manualmente.")
        server.server_close()


if __name__ == "__main__":
    main()
