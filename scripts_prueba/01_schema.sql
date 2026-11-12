-- =====================================================================
-- TiendaDB Lite — Esquema base para pruebas rápidas (RF-01)
-- Basado en init/01_schema.sql, compatible con validación AST y sandbox_db.
-- =====================================================================

DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS event_log CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS inventory CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- =====================================================================
-- categories — taxonomía de productos
-- =====================================================================
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    parent_id   INTEGER REFERENCES categories(id),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- =====================================================================
-- customers
-- =====================================================================
CREATE TABLE customers (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(150) UNIQUE NOT NULL,
    full_name       VARCHAR(200) NOT NULL,
    phone           VARCHAR(20),
    birth_date      DATE,
    city            VARCHAR(100),
    state           VARCHAR(100),
    country         VARCHAR(50) DEFAULT 'MX',
    loyalty_points  INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- =====================================================================
-- products
-- =====================================================================
CREATE TABLE products (
    id              SERIAL PRIMARY KEY,
    sku             VARCHAR(50) UNIQUE NOT NULL,
    name            VARCHAR(250) NOT NULL,
    description     TEXT,
    category_id     INTEGER REFERENCES categories(id),
    price           NUMERIC(10, 2) NOT NULL,
    cost            NUMERIC(10, 2),
    weight_kg       NUMERIC(8, 3),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- =====================================================================
-- inventory
-- =====================================================================
CREATE TABLE inventory (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER UNIQUE REFERENCES products(id),
    quantity        INTEGER NOT NULL DEFAULT 0,
    reorder_point   INTEGER DEFAULT 10,
    last_restock    TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- =====================================================================
-- orders — tabla transaccional principal
-- =====================================================================
CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    order_date      TIMESTAMP DEFAULT NOW(),
    status          VARCHAR(20) DEFAULT 'pending',
    total           NUMERIC(12, 2) NOT NULL,
    shipping_cost   NUMERIC(8, 2) DEFAULT 0,
    tax             NUMERIC(8, 2) DEFAULT 0,
    payment_method  VARCHAR(30),
    shipping_city   VARCHAR(100),
    shipping_state  VARCHAR(100),
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- =====================================================================
-- order_items — detalle de órdenes
-- =====================================================================
CREATE TABLE order_items (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES orders(id),
    product_id      INTEGER NOT NULL REFERENCES products(id),
    quantity        INTEGER NOT NULL,
    unit_price      NUMERIC(10, 2) NOT NULL,
    discount        NUMERIC(8, 2) DEFAULT 0,
    subtotal        NUMERIC(10, 2) NOT NULL
);

-- =====================================================================
-- reviews — reseñas de productos
-- =====================================================================
CREATE TABLE reviews (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES products(id),
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    rating          SMALLINT CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    is_verified     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- =====================================================================
-- event_log — bitácora de eventos
-- =====================================================================
CREATE TABLE event_log (
    id              BIGSERIAL PRIMARY KEY,
    customer_id     INTEGER REFERENCES customers(id),
    event_type      VARCHAR(50) NOT NULL,
    event_data      JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- =====================================================================
-- Índices iniciales
-- =====================================================================
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_products_is_active ON products(is_active);

CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);

CREATE INDEX idx_reviews_product_id ON reviews(product_id);
CREATE INDEX idx_reviews_customer_id ON reviews(customer_id);

CREATE INDEX idx_event_log_customer_id ON event_log(customer_id);
CREATE INDEX idx_event_log_created_at ON event_log(created_at);
CREATE INDEX idx_event_log_event_type ON event_log(event_type);

CREATE INDEX idx_categories_parent_id ON categories(parent_id);

COMMENT ON TABLE customers IS 'Customer master data';
COMMENT ON TABLE products IS 'Product catalog';
COMMENT ON TABLE orders IS 'Order header';
COMMENT ON TABLE order_items IS 'Order line items';
COMMENT ON TABLE inventory IS 'Stock per product';
COMMENT ON TABLE reviews IS 'Product reviews by customers';
COMMENT ON TABLE event_log IS 'Application event audit log';
COMMENT ON TABLE categories IS 'Product category taxonomy';

