/*
Banderas de build del frontend.

VITE_ENABLE_TIENDADB_SCAN: solo con el valor "true" el frontend llama a
/api/full-scan y a los detectores de TiendaDB. TiendaDB existe únicamente en el
entorno de desarrollo (docker-compose.yml); el build de producción no define la
variable, así que no hace esas solicitudes (Requirement 26 del E2).
En desarrollo la activa frontend/.env.development.
*/
export const TIENDADB_SCAN_ENABLED = import.meta.env.VITE_ENABLE_TIENDADB_SCAN === 'true'
