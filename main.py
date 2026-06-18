import traceback
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import cargar_historial, get_vector_connection
from pydantic import BaseModel
from agent import FinanceAgent
import uvicorn

app = FastAPI(
    title="Agente Financiero API",
    description="API financiero con RAG, MCP y Ollama",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    pregunta: str
    session_id: str | None = None
    
class AskResponse(BaseModel):
    respuesta: str
    herramientas_usadas: list[str]
    session_id: str
    
class ReportReponse(BaseModel):
    mensaje: str
    ruta_pdf: str
    
    
@app.get("/health")
async def health():
    """Verifica que el servidor este corriendo"""
    return {"status": "healthy"}



@app.get("/conversacion/{sesion_id}")
async def get_conversacion(session_id: str):
    historial = cargar_historial(session_id)
    return {"session_id": session_id, "mensajes": historial}


@app.delete("/conversacion/{sesion_id}")
async def delete_conversacion(sesion_id: str):
    conn = get_vector_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM conversaciones WHERE session_id = %s", (sesion_id,))
    conn.commit()
    conn.close()
    return {"mensaje": "Conversación eliminada"}


@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    import uuid
    """
    Recibe una pregunta en lenguaje natural y le responde consultando Postgres y documentos financieros (RAG).
    
    Ejemplo de Body:
    {
        "pregunta": "¿Cuanto gastamos de mas en enero 2025?"
    }
    """
    session_id = body.session_id or str(uuid.uuid4())
    
    if not body.pregunta.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")
    
    try:
        agent = FinanceAgent()
        respuesta, herramientas = await agent.run(body.pregunta, session_id)
        return AskResponse(respuesta=respuesta, herramientas_usadas=herramientas, session_id= session_id)
    
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/report/{anio}/{mes}", response_model=ReportReponse)
async def generate_report(anio: int, mes: int):
  """
  Genera un reporte financiero mensual en PDF.
  El agente analiza los datos y construye el contenido,
  luego la tool generar_reporte_pdf() lo exporta.
  
  Ejemplo: GET /report/2026/1 -> reporte de enero 2026
  
  """
  if mes < 1 or mes > 12:
      raise HTTPException(status_code=400, detail="El mes debe estar entre 1 y 12.")
  
  try:
      agent = FinanceAgent()
      pregunta = (
          f"Genera un reporte financiero completo del mes {mes} del anio {anio}. "
          f"Incluye ventas totales, gastos, comparacion vs presupuesto, "
          f"y cualquier contexto relevante de reportes anteriores. "
          f"Luego genera el PDF con toda esa informacion."
      )
      
      respuesta, _ = await agent.run(pregunta)
      
      from mcp_server import generar_reporte_pdf
      resultado = generar_reporte_pdf(mes=mes, año=anio, contenido=respuesta)
      
      return ReportReponse(mensaje=respuesta, ruta_pdf=resultado["ruta"])
  
  except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))
  
  
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
  
    