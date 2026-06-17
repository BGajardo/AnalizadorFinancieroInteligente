import psycopg2
from pgvector.psycopg2 import register_vector
from config import settings


def get_connection():
    conn = psycopg2.connect(settings.DATABASE_URL)
    return conn

def get_vector_connection():
    conn = psycopg2.connect(settings.DATABASE_URL)
    register_vector(conn)
    return conn

def crear_tablas():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    conn.commit()
    conn.close()
    
    conn = get_vector_connection()
    cur = conn.cursor();
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id      SERIAL PRIMARY KEY,
            fecha   DATE           NOT NULL,
            monto   DECIMAL(12, 2) NOT NULL,
            cliente VARCHAR(255),
            detalle TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id         SERIAL PRIMARY KEY,
            fecha      DATE           NOT NULL,
            monto      DECIMAL(12, 2) NOT NULL,
            categoria  VARCHAR(100)   NOT NULL,
            descripcion TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS presupuesto (
            id               SERIAL PRIMARY KEY,
            mes              INTEGER        NOT NULL,
            año              INTEGER        NOT NULL,
            ventas_esperadas DECIMAL(12, 2) NOT NULL,
            gastos_esperados DECIMAL(12, 2) NOT NULL,
            UNIQUE(mes, año)   -- no puede haber dos presupuestos para el mismo mes
        )
    """)
    
    cur.execute("""
                CREATE TABLE IF NOT EXISTS documentos(
                    id SERIAL PRIMARY KEY,
                    fuente VARCHAR(255) NOT NULL,
                    contenido TEXT NOT NULL,
                    embedding vector(768)
                )
                """)
    
    cur.execute("""
                CREATE INDEX IF NOT EXISTS documentos_embedding_idx
                ON documentos
                USING ivfflat (embedding vector_cosine_ops)
                """)
    
    
    
    conn.commit()
    conn.close()
    print("Tablas creadas correctamente")
    
    
def seed_data():
    """
    Inserta datos de ejemplo para que el agente tenga algo con qué trabajar.
    Solo correr si las tablas están vacías.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Ventas de enero y febrero 2026
    cur.execute("""
        INSERT INTO ventas (fecha, monto, cliente, detalle) VALUES
        ('2026-01-05', 15000.00, 'Empresa A', 'Consultoría mensual'),
        ('2026-01-12', 8500.00,  'Empresa B', 'Licencias software'),
        ('2026-01-20', 22000.00, 'Empresa C', 'Proyecto implementación'),
        ('2026-01-28', 5000.00,  'Empresa D', 'Soporte técnico'),
        ('2026-02-03', 18000.00, 'Empresa A', 'Consultoría mensual'),
        ('2026-02-15', 12000.00, 'Empresa E', 'Desarrollo a medida'),
        ('2026-02-22', 9500.00,  'Empresa B', 'Licencias software')
        ON CONFLICT DO NOTHING
    """)

    # Gastos de enero y febrero 2026
    cur.execute("""
        INSERT INTO gastos (fecha, monto, categoria, descripcion) VALUES
        ('2026-01-01', 8000.00,  'Sueldos',      'Nómina enero'),
        ('2026-01-10', 1200.00,  'Infraestructura', 'Servidores AWS'),
        ('2026-01-15', 500.00,   'Marketing',    'Campaña redes sociales'),
        ('2026-01-30', 300.00,   'Oficina',      'Arriendo coworking'),
        ('2026-02-01', 8000.00,  'Sueldos',      'Nómina febrero'),
        ('2026-02-10', 1200.00,  'Infraestructura', 'Servidores AWS'),
        ('2026-02-20', 800.00,   'Marketing',    'Campaña Google Ads')
        ON CONFLICT DO NOTHING
    """)

    # Presupuesto enero y febrero 2026
    cur.execute("""
        INSERT INTO presupuesto (mes, año, ventas_esperadas, gastos_esperados) VALUES
        (1, 2026, 45000.00, 12000.00),
        (2, 2026, 48000.00, 12000.00)
        ON CONFLICT (mes, año) DO NOTHING
    """)

    conn.commit()
    conn.close()
    print("Datos de ejemplo insertados correctamente")


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    crear_tablas()
    seed_data()