-- =====================================================================
-- TiendaDB Optimizada — Esquema con Mejores Prácticas PostgreSQL
-- Compatible con validación AST (RF-01.3) y ejecución en sandbox_db.
-- =====================================================================

-- Extensión permitida para búsquedas de texto con trigramas (evita Seq Scan en LIKE '%...%')
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DROP TABLE IF EXISTS resenas CASCADE;
DROP TABLE IF EXISTS eventos CASCADE;
DROP TABLE IF EXISTS detalle_ordenes CASCADE;
DROP TABLE IF EXISTS ordenes CASCADE;
DROP TABLE IF EXISTS inventario CASCADE;
DROP TABLE IF EXISTS productos CASCADE;
DROP TABLE IF EXISTS categorias CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;

-- =====================================================================
-- categorias — uso de GENERATED ALWAYS AS IDENTITY y TIMESTAMPTZ
-- =====================================================================
CREATE TABLE categorias (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL,
    padre_id    INTEGER REFERENCES categorias(id) ON DELETE SET NULL,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_categorias_padre_id ON categorias(padre_id);

-- =====================================================================
-- clientes
-- =====================================================================
CREATE TABLE clientes (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    correo            VARCHAR(150) UNIQUE NOT NULL,
    nombre_completo   VARCHAR(200) NOT NULL,
    telefono          VARCHAR(20),
    fecha_nacimiento  DATE,
    ciudad            VARCHAR(100),
    estado            VARCHAR(100),
    pais              CHAR(2) NOT NULL DEFAULT 'MX',
    puntos_lealtad    INTEGER NOT NULL DEFAULT 0 CHECK (puntos_lealtad >= 0),
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =====================================================================
-- productos — restricciones de dominio e índice GIN trigram
-- =====================================================================
CREATE TABLE productos (
    id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku           VARCHAR(50) UNIQUE NOT NULL,
    nombre        VARCHAR(250) NOT NULL,
    descripcion   TEXT,
    categoria_id  INTEGER NOT NULL REFERENCES categorias(id) ON DELETE RESTRICT,
    precio        NUMERIC(10, 2) NOT NULL CHECK (precio >= 0),
    costo         NUMERIC(10, 2) CHECK (costo IS NULL OR costo >= 0),
    peso_kg       NUMERIC(8, 3) CHECK (peso_kg IS NULL OR peso_kg > 0),
    activo        BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_productos_categoria_id ON productos(categoria_id);
CREATE INDEX idx_productos_activo ON productos(activo) WHERE activo = TRUE;
CREATE INDEX idx_productos_descripcion_trgm ON productos USING gin (descripcion gin_trgm_ops);

-- =====================================================================
-- inventario — fillfactor para HOT updates y autovacuum activo
-- =====================================================================
CREATE TABLE inventario (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producto_id     INTEGER UNIQUE NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    cantidad        INTEGER NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
    punto_reorden   INTEGER NOT NULL DEFAULT 10 CHECK (punto_reorden >= 0),
    ultimo_reabasto TIMESTAMPTZ,
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
) WITH (autovacuum_enabled = true, fillfactor = 90);

-- =====================================================================
-- ordenes — covering index en FK e índice parcial para estados minoritarios
-- =====================================================================
CREATE TABLE ordenes (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente_id      INTEGER NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    fecha_orden     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    estado          VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                    CHECK (estado IN ('pendiente', 'enviado', 'entregado', 'cancelado', 'reembolsado')),
    total           NUMERIC(12, 2) NOT NULL CHECK (total >= 0),
    costo_envio     NUMERIC(8, 2) NOT NULL DEFAULT 0 CHECK (costo_envio >= 0),
    impuesto        NUMERIC(8, 2) NOT NULL DEFAULT 0 CHECK (impuesto >= 0),
    metodo_pago     VARCHAR(30) NOT NULL,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cubre FK (cliente_id) para JOINs y DELETEs eficientes en ordenes
CREATE INDEX idx_ordenes_cliente_id ON ordenes(cliente_id);
-- Índice parcial selectivo para estados minoritarios distintos a 'pendiente'
CREATE INDEX idx_ordenes_estado_no_pendiente ON ordenes(estado) WHERE estado <> 'pendiente';

-- =====================================================================
-- detalle_ordenes — todas las llaves foráneas indexadas
-- =====================================================================
CREATE TABLE detalle_ordenes (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_id         INTEGER NOT NULL REFERENCES ordenes(id) ON DELETE CASCADE,
    producto_id      INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    cantidad         INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario  NUMERIC(10, 2) NOT NULL CHECK (precio_unitario >= 0),
    descuento        NUMERIC(8, 2) NOT NULL DEFAULT 0 CHECK (descuento >= 0),
    subtotal         NUMERIC(10, 2) NOT NULL CHECK (subtotal >= 0)
);

CREATE INDEX idx_detalle_ordenes_orden_id ON detalle_ordenes(orden_id);
CREATE INDEX idx_detalle_ordenes_producto_id ON detalle_ordenes(producto_id);

-- =====================================================================
-- resenas
-- =====================================================================
CREATE TABLE resenas (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producto_id  INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    cliente_id   INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    calificacion SMALLINT NOT NULL CHECK (calificacion BETWEEN 1 AND 5),
    comentario   TEXT,
    verificada   BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_resenas_producto_id ON resenas(producto_id);
CREATE INDEX idx_resenas_cliente_id ON resenas(cliente_id);

-- =====================================================================
-- eventos — particionada por rango mensual para retención eficiente
-- =====================================================================
CREATE TABLE eventos (
    id          BIGINT GENERATED ALWAYS AS IDENTITY,
    cliente_id  INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
    tipo_evento VARCHAR(50) NOT NULL,
    datos       JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_origen   INET,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (creado_en);

CREATE TABLE eventos_2026_10 PARTITION OF eventos
    FOR VALUES FROM ('2026-10-01 00:00:00+00') TO ('2026-11-01 00:00:00+00');

CREATE TABLE eventos_2026_11 PARTITION OF eventos
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');

CREATE TABLE eventos_default PARTITION OF eventos DEFAULT;

CREATE INDEX idx_eventos_cliente_id ON eventos(cliente_id);
CREATE INDEX idx_eventos_creado_en ON eventos(creado_en);

COMMENT ON TABLE categorias IS 'Taxonomía jerárquica de categorías';
COMMENT ON TABLE clientes IS 'Maestro de clientes';
COMMENT ON TABLE productos IS 'Catálogo de productos con búsqueda trigram';
COMMENT ON TABLE inventario IS 'Control de existencias por producto';
COMMENT ON TABLE ordenes IS 'Encabezado de órdenes con índice cubriente y parcial';
COMMENT ON TABLE detalle_ordenes IS 'Partidas de orden con FK indexadas';
COMMENT ON TABLE resenas IS 'Reseñas verificadas de clientes';
COMMENT ON TABLE eventos IS 'Bitácora particionada por mes para retención sencilla';
