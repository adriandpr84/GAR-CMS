#!/usr/bin/env python3
# ==============================================================================
# TrafficMix Generator para GAR (Version Python multihilo con urllib)
# Requisito 15: Generar tráfico desde fuera de la red y desde hot-desks
# ==============================================================================

import sys
import time
import random
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

# Endpoints aleatorios para simular comportamiento humano y forzar lecturas de DB
ENDPOINTS = [
    "/",
    "/wp-login.php",
    "/?s=test",
    "/?p=1",
    "/wp-cron.php"
]

def simular_usuario(url, end_time, thread_id):
    """Simula un único usuario haciendo peticiones secuenciales hasta llegar al end_time."""
    requests_sent = 0
    while time.time() < end_time:
        endpoint = random.choice(ENDPOINTS)
        target = f"{url}{endpoint}"
        
        try:
            # Crear un Request con un User-Agent para simular un navegador
            req = urllib.request.Request(
                target, 
                headers={'User-Agent': f'Mozilla/5.0 TrafficMix/1.0 (User-{thread_id})'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.status
                print(f"[{time.strftime('%H:%M:%S')}][Hilo-{thread_id}] Petición a {target} -> OK ({status})")
        except urllib.error.HTTPError as e:
            # Errores HTTP como 404, 500, 403 siguen siendo respuestas válidas de red
            print(f"[{time.strftime('%H:%M:%S')}][Hilo-{thread_id}] Petición a {target} -> OK/HTTP_CODE ({e.code})")
        except Exception as e:
            # Errores de red físicos, de DNS o timeouts
            print(f"[{time.strftime('%H:%M:%S')}][Hilo-{thread_id}] Petición a {target} -> ERROR ({e})")
            
        requests_sent += 1
        
        # Pausa aleatoria entre 0.1 y 1.5 segundos entre peticiones del mismo usuario
        time.sleep(random.uniform(0.1, 1.5))
        
    return requests_sent

def main():
    # Uso: ./trafficmix.py <URL_DEL_CMS> <SEGUNDOS_DE_DURACION> <CONCURRENCIA/HILOS>
    # Ejemplo: ./trafficmix.py http://192.168.1.10 60 5
    url = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.10"
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    # Eliminar barra diagonal final si existe
    if url.endswith('/'):
        url = url[:-1]

    print("=" * 70)
    print(f" Iniciando TrafficMix Generator hacia: {url}")
    print(f" Duración: {duration} segundos | Hilos concurrentes: {threads}")
    print("=" * 70)

    end_time = time.time() + duration

    # Ejecutar en hilos concurrentes utilizando el pool estándar
    with ThreadPoolExecutor(max_workers=threads) as executor:
        # Lanzar la simulación en paralelo
        futures = [
            executor.submit(simular_usuario, url, end_time, i + 1) 
            for i in range(threads)
        ]
        
        # Recopilar resultados (suma de peticiones enviadas por cada hilo)
        total_requests = sum(f.result() for f in futures)

    print("=" * 70)
    print(f" TrafficMix finalizado. Total peticiones enviadas: {total_requests}")
    print("=" * 70)

if __name__ == "__main__":
    main()
