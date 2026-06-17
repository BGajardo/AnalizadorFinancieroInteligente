import httpx
import psycopg2
from pgvector.psycopg import register_vector
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from mcp.server import FastMCP
from config import settings
from database import get_vector_connection

mcp = FastMCP("finance-tools")

def get_connection():
    return get_vector_connection()



async def generar_embedding(texto:str) -> list[float]:
    """
    Llama a Ollama para convertir un texto en vector.
    Se usa internamente en buscar_documentos() para indexar los documentos financieros(No es una tool del agente).
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": settings.OLLAMA_EMBEDDING_MODEL,
                "input": texto
            }
        )
        return response.json()["embedding"]
  
  
@mcp.tool
def get_ventas(mes:int, año:int) -> dict:
    """
    Obtiene el total de ventas de un mes y año especifico.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            SUM(monto) as total_ventas,
            COUNT(*) as cantidad_transacciones,
            AVG(monto) as promedio_por_transaccion
        FROM ventas
        WHERE EXTRACT(MONTH FROM fecha) = %s
        AND EXTRACT(YEAR FROM fecha) = %s
        """, (mes, año))
    row = cur.fetchone()
    conn.close()
    return{
        "mes": mes,
        "año": año,
        "total_ventas": float(row[0] or 0),
        "cantidad_transacciones": int(row[1] or 0),
        "promedio_por_transaccion": float(row[2] or 0)
    }
    
    
@mcp.tool
def get_gastos(mes: int, año:int) -> dict:
    """
    Obtiene el total de gastos de un mes y año especifico.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            categoria
            SUM(monto) as total,
        FROM gastos
        WHERE EXTRACT(MONTH FROM fecha) = %s
        AND EXTRACT(YEAR FROM fecha) = %s
        GROUP BY categoria
        ORDER BY total DESC
        """, (mes, año))
    rows = cur.fetchall()
    conn.close()
    
    categorias = [{"categoria": r[0], "total": float(r[1])}for r in rows]
    total = sum(c["total"] for c in categorias)
    
    return{
        "mes": mes,
        "año": año,
        "total": total,
        "categorias": categorias
        }
    
@mcp.tool
def get_presupuesto(mes:int, año:int) -> dict:
    """
    Obtiene el presupuesto planificado para un mes y año especifico.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
                SELECT ventas_esperadas, gastos_esperados
                FROM presupuesto
                WHERE mes = %s AND año = %s
                """, (mes, año))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return {"error": f"No se encontró presupuesto para ese {mes}/{año}"}
    
    return {
        "mes": mes,
        "año": año,
        "ventas_esperadas": float(row[0]),
        "gastos_esperados": float(row[1])
    }
    
    
@mcp.tool
def comparar_vs_presupuesto(mes:int, año:int) -> dict:
    """
    Compara ventas y gastos relaes contra el presupuesto.
    Retorna las diferencias y si se cumplio o no cada meta.
    """
    ventas = get_ventas(mes, año)
    gastos = get_gastos(mes, año)
    presupuesto = get_presupuesto(mes, año)
    
    if "error" in presupuesto:
        return presupuesto
    
    diff_ventas = ventas["total_ventas"] - presupuesto["ventas_esperadas"]
    diff_gastos = gastos["total"] - presupuesto["gastos_esperados"]
    
    
    return {
        "mes": mes,
        "año": año,
        "ventas": {
            "reales": ventas["total_ventas"],
            "presupuesto": presupuesto["ventas_esperadas"],
            "diferencia": diff_ventas,
            "cumplido": diff_ventas >= 0
        },
        "gastos": {
            "reales": gastos["total"],
            "presupuesto": presupuesto["gastos_esperados"],
            "diferencia": diff_gastos,
            "cumplido": diff_gastos <= 0
        }
    }
    
    
@mcp.tool
async def buscar_documentos(query:str, limite: int=3) -> list[dict]:
    """
    Busca en documentos financieros historicos usando similitud semantica.
    Util para preguntas sobre reportes anteriores, politicas o contextos historicos
    """
    vector = await generar_embedding(query)
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            contenido,
            fuente,
            1 - (embedding <-> %s::vector) AS similitud
        FROM documentos
        ORDER BY embedding <-> %s::vector
        LIMIT %s
    """, (vector, vector, limite))
    
    rows = cur.fetchall()
    conn.close()
    
    return [{"contenido": r[0], "fuente": r[1], "similitud": round(float(r[2]), 4)} for r in rows]

@mcp.tool()
def generar_reporte_pdf(mes: int, año: int, contenido: str) -> dict:
    """
    Genera un PDF con el análisis financiero del mes.
    El parámetro contenido es el análisis redactado por el agente.
    """
    import os
    os.makedirs("reportes", exist_ok=True)

    ruta = f"reportes/{año}_{mes:02d}_reporte.pdf"
    c = canvas.Canvas(ruta, pagesize=A4)
    ancho, alto = A4


    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, alto - 60, f"Reporte Financiero — {mes:02d}/{año}")


    c.setLineWidth(0.5)
    c.line(50, alto - 75, ancho - 50, alto - 75)

  
    c.setFont("Helvetica", 11)
    y = alto - 100
    for linea in contenido.split("\n"):
        if y < 60:         
            c.showPage()
            c.setFont("Helvetica", 11)
            y = alto - 60
        c.drawString(50, y, linea[:100])  
        y -= 16

    c.save()

    return {
        "mensaje": "PDF generado correctamente",
        "ruta":    ruta
    }

if __name__ == "__main__":
    mcp.run()