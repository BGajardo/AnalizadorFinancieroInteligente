from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    
class AskResponse(BaseModel):
    respuesta: str
    herramientas_usadas: list[str]
    
class ReportReponse(BaseModel):
    mensaje: str
    ruta_pdf: str
    
    
@app.get("/health")
async def health():
    """Verifica que el servidor este corriendo"""
    return {"status": "healthy"}

@app.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    """
    Recibe una pregunta en lenguaje natural y le responde consultando Postgres y documentos financieros (RAG).
    
    Ejemplo de Body:
    {
        "pregunta": "¿Cuanto gastamos de mas en enero 2025?"
    }
    """
    if not body.pregunta.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")
    
    try:
        agent = FinanceAgent()
        respuesta, herramientas = agent.run(body.pregunta)
        return AskResponse(respuesta=respuesta, herramientas_usadas=herramientas)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.get("/report/{año}/{mes}", response_model=ReportReponse)
async def generate_report(año: int, mes: int):
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
          f"Genera un reporte financiero completo del mes {mes} del año {año}. "
          f"Incluye ventas totales, gastos, comparacion vs presupuesto, "
          f"y cualquier contexto relevante de reportes anteriores. "
          f"Luego genera el PDF con toda esa informacion."
      )
      
      respuesta, _ = agent.run(pregunta)
      
      return ReportReponse(mensaje=respuesta, ruta_pdf=f"reportes/{año}_{mes:02d}_reporte.pdf")
  
  except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))
  
  
  if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
  
    