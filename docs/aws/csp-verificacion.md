# Verificación de la Content-Security-Policy (T-06)

Trazabilidad: RF-04.5 · CA-13 · Requirement 5 (criterios 5.4 y 5.5) · Tarea T-06.

Este documento describe cómo comprobar que el build de producción del frontend funciona con la CSP que envía Caddy, y registra cada directiva que se añade a la CSP inicial.

## 1. CSP vigente

CSP inicial (R5.3):

```text
default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'
```

CSP vigente en el `Caddyfile` (snippet `security_headers`), tras la revisión estática de la sección 3:

```text
default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; frame-ancestors 'none'
```

## 2. Procedimiento de verificación manual

### 2.1 Levantar el build de producción en local

1. Copiar la plantilla de entorno y ajustarla para modo HTTP local:

   ```powershell
   Copy-Item .env.prod.example .env
   ```

   En `.env`, para la prueba local: `APP_DOMAIN=:80`, `VITE_API_URL=/api`, `CORS_ORIGINS=http://localhost` y `COOKIE_SECURE=false`. Rellenar los secretos (`JWT_SECRET`, `APP_DB_*`, `SANDBOX_DB_*`) con valores de prueba.

2. Construir y levantar los cinco contenedores:

   ```powershell
   docker compose -f docker-compose.prod.yml up -d --build
   docker compose -f docker-compose.prod.yml ps
   ```

3. Confirmar que Caddy envía la CSP vigente (sección 1):

   ```powershell
   curl.exe -sI http://localhost/ | Select-String "Content-Security-Policy"
   ```

En el servidor EC2 el procedimiento es el mismo, abriendo `https://<dominio>` en lugar de `http://localhost`.

### 2.2 Recorrer las pantallas con la consola abierta

1. Abrir una ventana privada del navegador (sin extensiones, que también generan avisos de CSP) en `http://localhost/`.
2. Abrir las herramientas de desarrollo (F12), pestaña **Console**, y activar **Preserve log** para no perder mensajes al navegar.
3. Recargar la página con la consola ya abierta (Ctrl+Shift+R) y recorrer:
   1. **Login**: pantalla inicial, iniciar sesión con un usuario válido y uno inválido.
   2. **Registro**: crear un usuario nuevo, incluido un intento con contraseña que rechace la política.
   3. **Análisis**: lanzar un análisis nuevo, abrir las pestañas de resultados (overview, índices, consultas, bloat, configuración, salud), copiar una recomendación SQL y abrir el historial.
4. En **Network**, revisar también que ninguna petición aparece como `(blocked:csp)`.

### 2.3 Leer las violaciones

Cada violación aparece en la consola como error, con un texto parecido a:

- Chrome/Edge: `Refused to load the stylesheet 'https://ejemplo.com/a.css' because it violates the following Content Security Policy directive: "style-src 'self' 'unsafe-inline'".`
- Firefox: `Content-Security-Policy: The page's settings blocked the loading of a resource at https://ejemplo.com/a.css ("style-src").`

De cada mensaje se anotan tres datos: la **fuente bloqueada** (URL o esquema, p. ej. `https://ejemplo.com`, `blob:`, `inline`, `eval`), la **directiva** que la bloqueó (si el mensaje cita `default-src`, la directiva efectiva es la específica del tipo de recurso: `script-src`, `font-src`, `connect-src`, etc.) y la **pantalla** donde ocurrió.

### 2.4 Ampliar la CSP

Regla (R5.5): ampliar **solo** la directiva del tipo de recurso bloqueado y **solo** con la fuente bloqueada.

- Usar el origen concreto (`https://fonts.gstatic.com`), nunca comodines (`*`, `https:`).
- Si la directiva no existe, crearla partiendo de `'self'` (p. ej. `font-src 'self' <fuente>`), porque al declararla deja de heredar de `default-src`.
- No añadir `'unsafe-eval'` ni `'unsafe-inline'` en `script-src`. Si una violación los exige, se registra y se corrige el frontend.
- No tocar `frame-ancestors 'none'`.

Después de editar el `Caddyfile`:

```powershell
docker compose -f docker-compose.prod.yml restart proxy
```

Registrar el cambio en la tabla de la sección 4 y repetir el recorrido 2.2 completo. El ciclo termina cuando una pasada completa por login, registro y análisis muestra **0 violaciones de CSP** (R5.4).

## 3. Revisión estática del frontend

Revisión del código de `frontend/` (fecha: 2026-11-24) para anticipar violaciones antes de la prueba en navegador.

| Elemento revisado | Hallazgo | Efecto con la CSP inicial | Acción |
| --- | --- | --- | --- |
| `frontend/index.html`, hoja de estilos de Google Fonts (`https://fonts.googleapis.com/css2?family=Inter...&family=JetBrains+Mono...`) | Hoja de estilos externa | Bloqueada por `style-src 'self' 'unsafe-inline'` | Se añade `https://fonts.googleapis.com` a `style-src` (registro 1) |
| Archivos de fuente que carga esa hoja (`https://fonts.gstatic.com/...woff2`) | Fuentes externas | Bloqueadas: no hay `font-src`, se aplica `default-src 'self'` | Se crea `font-src 'self' https://fonts.gstatic.com` (registro 2) |
| `<link rel="preconnect">` a ambos orígenes | Solo pista de conexión | No lo controla la CSP | Ninguna |
| `<script type="module" src="/src/main.jsx">` | Vite lo compila a un bundle en `/assets/` del mismo origen; no genera scripts inline | Permitido por `default-src 'self'` | Ninguna |
| `frontend/src/api/pgguardian.js` (`fetch` a `API_BASE`) | En producción `VITE_API_URL` es `/api` (por defecto en `docker-compose.prod.yml`) o `https://<dominio>/api` (`.env.prod.example`): mismo origen | Permitido por `default-src 'self'` | Ninguna, siempre que `VITE_API_URL` apunte al mismo dominio que sirve Caddy |
| Atributos `style={{...}}` en componentes React (`DataTable`, `HealthScore`, páginas con `skeleton`) | React los aplica por CSSOM | Permitido (`'unsafe-inline'` en `style-src`) | Ninguna |
| `navigator.clipboard.writeText` en `SqlRecommendation.jsx` | API del navegador | No lo controla la CSP | Ninguna |
| `eval`, `new Function`, WebSocket, `blob:`, `iframe`, workers, `@import` o `url()` externos en CSS | No encontrados | — | Ninguna |
| Imágenes y SVG (`/Logo.svg`, `public/`, `src/assets/`) | Mismo origen | Permitido por `img-src 'self' data:` | Ninguna |

Estado: la revisión estática encontró dos fuentes que la CSP inicial bloquea con certeza y ya se añadieron al `Caddyfile`. **La verificación manual en navegador (sección 2) sigue pendiente** y es la que cierra CA-13.

## 4. Registro de directivas ampliadas

| # | Fecha | Pantalla | Mensaje de violación | Directiva | Fuente añadida | Justificación | Responsable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-24 | Todas (`index.html`) | Previsto por revisión estática: carga de hoja de estilos `https://fonts.googleapis.com/css2?...` bloqueada por `style-src` | `style-src` | `https://fonts.googleapis.com` | Hoja de estilos de las fuentes Inter y JetBrains Mono enlazada en `frontend/index.html` | Revisión estática (T-06); confirmar en navegador |
| 2 | 2026-11-24 | Todas (`index.html`) | Previsto por revisión estática: carga de fuente `https://fonts.gstatic.com/...woff2` bloqueada por `default-src` (sin `font-src`) | `font-src` (nueva) | `'self' https://fonts.gstatic.com` | Archivos de fuente que referencia la hoja de Google Fonts | Revisión estática (T-06); confirmar en navegador |

## 5. Resultado de la verificación en navegador

Completar tras cada pasada del procedimiento 2.2.

| Fecha | Entorno (local / EC2) | Navegador y versión | Login | Registro | Análisis | Violaciones de CSP | Responsable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

Criterio de cierre (CA-13): una fila con 0 violaciones en las tres pantallas, sobre el build de producción.
