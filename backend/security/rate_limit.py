"""
PgGuardian — Limitador de Tasa (Rate Limiting) por IP (RNF-02)

Implementa una ventana deslizante en memoria segura para hilos, sin dependencias
externas ni Redis, limitando las peticiones POST de login y registro a un máximo
de 10 solicitudes por minuto por dirección IP.
"""

from collections import defaultdict, deque
import math
import os
import threading
import time

from fastapi import Request

AUTH_RATE_LIMIT_MAX_REQUESTS = 10
AUTH_RATE_LIMIT_WINDOW_SECONDS = 60


def extract_client_ip(request: Request) -> str:
    """Obtiene la IP del cliente respetando proxy solo cuando TRUST_PROXY_HEADERS=true."""
    if os.getenv("TRUST_PROXY_HEADERS", "").lower() == "true":
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            first_hop = forwarded.split(",", 1)[0].strip()
            if first_hop:
                return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class SlidingWindowRateLimiter:
    """Controla la tasa máxima de peticiones por clave (ruta + IP) en ventana móvil."""

    def __init__(
        self,
        *,
        max_requests: int = AUTH_RATE_LIMIT_MAX_REQUESTS,
        window_seconds: int = AUTH_RATE_LIMIT_WINDOW_SECONDS,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        """Limpia el estado en memoria (útil para aislamiento en pruebas)."""
        with self._lock:
            self._buckets.clear()

    def check(self, route_key: str, client_ip: str) -> tuple[bool, int]:
        """Registra un intento si hay cupo; devuelve (permitido, retry_after_segundos)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        key = (route_key, client_ip)

        with self._lock:
            queue = self._buckets[key]
            while queue and queue[0] <= cutoff:
                queue.popleft()

            if len(queue) >= self.max_requests:
                retry_after = max(1, int(math.ceil(queue[0] + self.window_seconds - now)))
                return False, retry_after

            queue.append(now)

            # Evita crecimiento ilimitado en memoria si llegan múltiples IPs transitorias.
            if len(self._buckets) > 4096:
                stale_keys = [
                    k for k, q in self._buckets.items() if not q or q[-1] <= cutoff
                ]
                for stale in stale_keys:
                    del self._buckets[stale]

            return True, 0


auth_rate_limiter = SlidingWindowRateLimiter()

