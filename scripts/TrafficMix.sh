#!/bin/bash
# ==============================================================================
# TrafficMix - Generador de tráfico para el CMS (Req. 15)
# Simula visitas reales aleatorias hacia el Load Balancer.
# ==============================================================================

TARGET="http://192.168.1.10" # IP fija del load-balancer según el inventario

echo "==============================================="
echo "  🚀 Iniciando TrafficMix hacia $TARGET"
echo "  Pulsa Ctrl+C para detener."
echo "==============================================="

# Rutas típicas de WordPress para simular comportamiento real
RUTAS=(
    "/"
    "/wp-login.php"
    "/wp-admin/"
    "/index.php/2026/05/hello-world/"
    "/feed/"
)

while true; do
  # Seleccionar una ruta aleatoria del array
  RUTA_ELEGIDA=${RUTAS[$RANDOM % ${#RUTAS[@]}]}
  
  # Hacer la petición y medir el tiempo
  echo -n "[$(date +'%H:%M:%S')] GET $RUTA_ELEGIDA -> "
  curl -s -o /dev/null -w "Status: %{http_code} | Tiempo: %{time_total}s\n" "$TARGET$RUTA_ELEGIDA"
  
  # A veces, alguien intenta acceder a una ruta que no existe (Errores 404)
  if [ $((RANDOM % 10)) -eq 0 ]; then
    echo -n "[$(date +'%H:%M:%S')] GET /ruta-inventada-$RANDOM -> "
    curl -s -o /dev/null -w "Status: %{http_code} | Tiempo: %{time_total}s\n" "$TARGET/ruta-inventada-$RANDOM"
  fi
  
  # Pausa aleatoria entre 0.5 y 3 segundos para no saturar la red
  sleep $(awk -v min=0.5 -v max=3 'BEGIN{srand(); print min+rand()*(max-min)}')
done
