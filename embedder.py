import os 
import httpx
import psycopg2
from PyPDF2 import PdfReader
from database import get_vector_connection
from config import settings

def leer_pdf(ruta: str) -> str:
    """Extrae todo el texto de un PDF."""
    reader = PdfReader(ruta)
    texto = ""
    for pagina in reader.pages:
        texto += pagina.extract_text() or ""
    return texto

def leer_txt(ruta: str) -> str:
    """Lee un archivo de texto plano."""
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()
    
def dividir_en_chunks(texto: str, tamaño: int = 500, solapamiento: int = 50)-> list[str]:
    """
    Divide el texto en chunks de tamaño fijo con solapamiento.
    """
    chunks = []
    inicio = 0
    while inicio < len(texto):
        fin = inicio + tamaño
        chunks.append(texto[inicio:fin])
        inicio += tamaño - solapamiento
    return chunks


async def generar_embedding(texto:str) -> list[float]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": settings.OLLAMA_EMBEDDING_MODEL,
                "prompt": texto
            },
            timeout=30.0
            )
        return response.json()["embedding"]
    
    
async def indexar_documento(ruta: str):
    """
    Lee un archivo, se divide en chunks, genera embeddings y lo guarda en el pgvector
    """
    nombre = os.path.basename(ruta)
    extension = ruta.split(".")[-1].lower()
    
    print(f"\nIndexando: {nombre}")
    
    if extension == "pdf":
        texto = leer_pdf(ruta)
    elif extension == "txt":
        texto = leer_txt(ruta)
    else:
        print(f"Formato no Soportado: {extension}, saltando...")
        return
    
    if not texto.strip():
        print(f"Archivo vacio, saltando...")
        return
    
    chunks = dividir_en_chunks(texto)
    print(f"{len(chunks)} chunks generados")
    
    conn = get_vector_connection()
    cur = conn.cursor()
    
    
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue

        embedding = await generar_embedding(chunk)

        cur.execute("""
            INSERT INTO documentos (fuente, contenido, embedding)
            VALUES (%s, %s, %s::vector)
        """, (nombre, chunk, embedding))

        print(f"  chunk {i + 1}/{len(chunks)} indexado", end="\r")

    conn.commit()
    conn.close()
    print(f"  ✓ {nombre} indexado correctamente")
    
    
async def indexar_carpeta(carpeta: str = "documentos"):
    """
    Recorre la carpeta y indexa todos los PDFs y TXTs que encuentra.
    """
    if not os.path.exists(carpeta):
        print(f"Carpeta '{carpeta}' no encontrada, creándola...")
        os.makedirs(carpeta)
        print(f"Agrega tus PDFs o TXTs en '{carpeta}/' y vuelve a correr este script")
        return

    archivos = [
        f for f in os.listdir(carpeta)
        if f.endswith(".pdf") or f.endswith(".txt")
    ]

    if not archivos:
        print(f"No hay archivos en '{carpeta}/'")
        return

    print(f"Encontrados {len(archivos)} archivos para indexar")

    for archivo in archivos:
        ruta = os.path.join(carpeta, archivo)
        await indexar_documento(ruta)

    print("\n✓ Indexación completa")
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(indexar_carpeta())