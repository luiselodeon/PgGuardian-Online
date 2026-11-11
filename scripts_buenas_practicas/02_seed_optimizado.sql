-- =====================================================================
-- TiendaDB Optimizada — Carga inicial limpia y estadísticas al día
-- =====================================================================

SET client_min_messages = WARNING;

-- 10 categorías jerárquicas
INSERT INTO categorias (nombre, padre_id)
SELECT
    'Categoría ' || i,
    CASE WHEN i > 5 THEN ((i % 5) + 1) ELSE NULL END
FROM generate_series(1, 10) i;

-- 50 clientes
INSERT INTO clientes (correo, nombre_completo, telefono, fecha_nacimiento, ciudad, estado, puntos_lealtad)
SELECT
    'cliente' || i || '@ejemplo.mx',
    'Cliente ' || i || ' Demo',
    '+52' || (5500000000 + i)::text,
    DATE '1980-01-01' + (i * 120),
    (ARRAY['Ciudad de México', 'Guadalajara', 'Monterrey', 'Querétaro', 'Puebla'])[1 + (i % 5)],
    (ARRAY['CDMX', 'JAL', 'NL', 'QRO', 'PUE'])[1 + (i % 5)],
    (i * 25)
FROM generate_series(1, 50) i;

-- 30 productos
INSERT INTO productos (sku, nombre, descripcion, categoria_id, precio, costo, peso_kg, activo)
SELECT
    'SKU-OPT-' || lpad(i::text, 4, '0'),
    'Producto Optimizado ' || i,
    'Descripción estructurada para búsqueda por trigramas del producto ' || i,
    1 + (i % 10),
    (100 + i * 35.50)::numeric(10, 2),
    (50 + i * 18.25)::numeric(10, 2),
    (0.5 + (i % 5))::numeric(8, 3),
    TRUE
FROM generate_series(1, 30) i;

-- 30 registros de inventario
INSERT INTO inventario (producto_id, cantidad, punto_reorden, ultimo_reabasto)
SELECT
    p.id,
    100 + (p.id * 5),
    15,
    NOW() - INTERVAL '7 days'
FROM productos p;

-- 80 órdenes
INSERT INTO ordenes (cliente_id, fecha_orden, estado, total, costo_envio, impuesto, metodo_pago, creado_en)
SELECT
    1 + (i % 50),
    NOW() - ((i % 30) || ' days')::interval,
    CASE WHEN i % 10 = 0 THEN 'entregado' ELSE 'pendiente' END,
    (250 + i * 12.50)::numeric(12, 2),
    50.00,
    40.00,
    (ARRAY['tarjeta_credito', 'tarjeta_debito', 'transferencia'])[1 + (i % 3)],
    NOW() - ((i % 30) || ' days')::interval
FROM generate_series(1, 80) i;

-- 160 partidas de orden
INSERT INTO detalle_ordenes (orden_id, producto_id, cantidad, precio_unitario, descuento, subtotal)
SELECT
    o.id,
    1 + ((o.id + gs) % 30),
    1 + (gs % 3),
    199.00,
    0.00,
    199.00 * (1 + (gs % 3))
FROM ordenes o
CROSS JOIN generate_series(1, 2) gs;

-- 40 reseñas
INSERT INTO resenas (producto_id, cliente_id, calificacion, comentario, verificada)
SELECT
    1 + (i % 30),
    1 + (i % 50),
    4 + (i % 2),
    'Excelente producto, entrega rápida #' || i,
    TRUE
FROM generate_series(1, 40) i;

-- 60 eventos en particiones recientes
INSERT INTO eventos (cliente_id, tipo_evento, datos, ip_origen, creado_en)
SELECT
    1 + (i % 50),
    (ARRAY['vista_producto', 'agregar_carrito', 'compra'])[1 + (i % 3)],
    jsonb_build_object('origen', 'web', 'item', i),
    ('10.0.1.' || (1 + (i % 200)))::inet,
    TIMESTAMPTZ '2026-11-05 12:00:00+00' + (i || ' minutes')::interval
FROM generate_series(1, 60) i;

-- Actualizar estadísticas completas de todas las tablas (incluidas particiones)
ANALYZE categorias;
ANALYZE clientes;
ANALYZE productos;
ANALYZE inventario;
ANALYZE ordenes;
ANALYZE detalle_ordenes;
ANALYZE resenas;
ANALYZE eventos;

