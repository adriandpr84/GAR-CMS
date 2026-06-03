# Diagrama de Conexiones y Rutas (Fase 1: Aprovisionamiento)

## 1. Topología de Red

La infraestructura base se divide en dos segmentos principales (`main` e `internal`), orquestados durante esta fase inicial por el nodo Jumpstart. 
De acuerdo con los requisitos del diseño estructural, la red `internal` albergará los futuros nodos de base de datos y monitorización, mientras que la red `main` contendrá los frontales y puestos de empleado. En el estado actual (Baremetal), todas las máquinas han sido desplegadas a nivel de sistema operativo y conectadas a sus respectivos switches virtuales.

```mermaid
graph TD
    Internet((Internet)) <--> |NAT| Jumpstart[Jumpstart Node]
    Jumpstart <--> |enp0s9: 192.168.1.254| MainNet[Red Main: 192.168.1.0/24]
    Jumpstart <--> |enp0s10: 192.168.2.254| InternalNet[Red Internal: 192.168.2.0/24]

    subgraph Red Main
        LB[Load Balancer]
        WF1[Web Frontend 1]
        WF2[Web Frontend 2]
        HD[Hot-desks 1-8]
    end

    subgraph Red Internal
        DBM1[DB Master 1]
        DBM2[DB Master 2]
        DBW1[DB Worker 1]
        DBW2[DB Worker 2]
        MN[Monitoring Node]
        ST[Storage Node]
    end

    MainNet --- LB
    MainNet --- WF1
    MainNet --- WF2
    MainNet --- HD

    InternalNet --- DBM1
    InternalNet --- DBM2
    InternalNet --- DBW1
    InternalNet --- DBW2
    InternalNet --- MN
    InternalNet --- ST
```

