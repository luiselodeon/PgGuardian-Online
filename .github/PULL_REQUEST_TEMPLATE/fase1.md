# Fase 1: cambios de código y configuración (T-01 a T-07 y frontend)

<!--
Plantilla para el PR de la Fase 1 (T-08, Requirement 7.8).
Úsala abriendo el PR con ?template=fase1.md en la URL de comparación.
No abras el PR si algún criterio queda como no_aprobado (R7.7).
-->

## Cambios incluidos

- [ ] T-01: `JWT_SECRET` obligatorio en `docker-compose.prod.yml`
- [ ] T-02: rotación de logs con `x-logging`
- [ ] T-03: `mem_limit` por contenedor
- [ ] T-04: bind mount del sandbox con `create_host_path: false`
- [ ] T-05 y T-06: cabeceras de seguridad y CSP en `Caddyfile`
- [ ] T-07: `/api/health-check` saneado
- [ ] Frontend sin llamadas a endpoints de TiendaDB (R26)

## Verificación local (T-08)

Comando ejecutado (marca uno):

- [ ] `powershell -ExecutionPolicy Bypass -File scripts\verify_phase1.ps1`
- [ ] `bash scripts/verify_phase1.sh`

Fecha (AAAA-MM-DD): 
Ejecutado por: 

Pega aquí la tabla «Resumen para la descripción del PR» que imprime el script:

| Criterio | Requisito | Estado | Detalle |
| --- | --- | --- | --- |
| arranque | R7 | | |
| CA-09 | R1 | | |
| CA-10 | R2 | | |
| CA-11 | R3 | | |
| CA-12 | R4 | | |
| CA-13 | R5 | | |
| CA-14 | R6 | | |

Líneas JSON completas (opcional):

```text

```

- [ ] El script terminó con código 0 (todos los criterios `aprobado`).
