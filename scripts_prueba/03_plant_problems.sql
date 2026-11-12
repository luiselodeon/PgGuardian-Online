-- =====================================================================
-- TiendaDB Lite — Problemas plantados reducidos para pruebas rápidas
-- Basado en init/03_plant_problems.sql, ejecutable en sandbox_db
-- =====================================================================

SET client_min_messages = WARNING;

-- H01: orders.customer_id sin índice en llave foránea
DROP INDEX IF EXISTS idx_orders_customer_id;

-- H02: Índice duplicado en products(category_id)
CREATE INDEX idx_products_category_dup ON products(category_id);

-- H03: Índice en customers.birth_date
CREATE INDEX idx_customers_birth_date_unused ON customers(birth_date);

-- H06: Bloat ligero simulado en event_log
ALTER TABLE event_log SET (autovacuum_enabled = false);

DO $$
DECLARE
    i INTEGER;
BEGIN
    FOR i IN 1..3 LOOP
        UPDATE event_log SET event_data = event_data || jsonb_build_object('iteration', i)
        WHERE id IN (SELECT id FROM event_log ORDER BY random() LIMIT 50);
    END LOOP;

    DELETE FROM event_log WHERE id IN (SELECT id FROM event_log ORDER BY random() LIMIT 60);
END $$;

ALTER TABLE event_log SET (autovacuum_enabled = true);

-- H07: Autovacuum desactivado permanentemente en inventory
ALTER TABLE inventory SET (autovacuum_enabled = false);

-- H08: Dead tuples acumulados en reviews
ALTER TABLE reviews SET (autovacuum_enabled = false);

DO $$
DECLARE
    i INTEGER;
BEGIN
    FOR i IN 1..2 LOOP
        UPDATE reviews SET comment = comment || ' [edited ' || i || ']'
        WHERE id IN (SELECT id FROM reviews ORDER BY random() LIMIT 50);
    END LOOP;
END $$;

ALTER TABLE reviews SET (autovacuum_enabled = true);

-- H10: Estadísticas obsoletas en products (insertar 400 filas sin ANALYZE)
INSERT INTO products (sku, name, description, category_id, price, cost, weight_kg, is_active)
SELECT
    'SKU-NEW-' || i,
    'New Product ' || i,
    'New product description with extra content to be detected',
    1 + (i % 10),
    (random() * 1000)::numeric(10, 2),
    (random() * 500)::numeric(10, 2),
    (random() * 5)::numeric(8, 3),
    TRUE
FROM generate_series(1, 400) i;

-- H18: Registros antiguos sin política de retención en event_log
INSERT INTO event_log (customer_id, event_type, event_data, ip_address, user_agent, created_at)
SELECT
    1 + floor(random() * 100)::int,
    'page_view',
    '{}'::jsonb,
    '127.0.0.1'::inet,
    'old-agent',
    NOW() - INTERVAL '2 years' - (random() * 365 || ' days')::interval
FROM generate_series(1, 100) i;

-- Actualizar estadísticas excepto products (intencional para H10)
ANALYZE orders;
ANALYZE order_items;
ANALYZE event_log;
ANALYZE reviews;
ANALYZE customers;
ANALYZE inventory;
ANALYZE categories;

DO $$
BEGIN
    RAISE NOTICE 'TiendaDB Lite lista para pruebas rápidas';
END $$;

