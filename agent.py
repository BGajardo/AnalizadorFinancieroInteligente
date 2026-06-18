import json
import asyncio
from openai import OpenAI
from database import cargar_historial, guardar_mensaje
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from config import settings


SYSTEM_PROMPT = """
Eres un analista financiero experto. Tienes acceso a herramientas 
para consultar datos reales de la empresa.

Reglas:
- Siempre usa las herramientas para obtener datos reales, nunca inventes números
- Piensa paso a paso antes de responder
- Cuando termines de recopilar datos, redacta una respuesta clara y estructurada
- Siempre indica de qué fuente vienen los datos (base de datos o documentos históricos)
- Si necesitas varios datos, llama las herramientas de una en una

Herramientas disponibles y cuándo usarlas:
- get_ventas: para consultar ventas reales de un mes/año específico
- get_gastos: para consultar gastos reales de un mes/año específico
- get_presupuesto: para consultar el presupuesto planificado de un mes/año
- comparar_vs_presupuesto: para comparar real vs presupuesto de un mes/año
- buscar_documentos: SIEMPRE que la pregunta mencione reportes anteriores, 
  tendencias históricas, recomendaciones pasadas, políticas, o cualquier 
  contexto que no sea un dato numérico directo. También úsala para 
  complementar cualquier comparación entre períodos distintos.
- generar_reporte_pdf: cuando el usuario pida generar o exportar un reporte
"""


class FinanceAgent:
    
        def __init__(self):
            self.client = OpenAI(
                base_url=settings.OLLAMA_URL,
                api_key="ollama",
            )
            
            self.model = settings.OLLAMA_MODEL
        
        async def run(self, pregunta:str, session_id:str) -> tuple[str, list[str]]:
            """
            Ejecuta el agent loop completo.
            Retorna la respuesta final y una lista de herramientas usadas.
            """
            
            
            server_params = StdioServerParameters(
                command="python",
                args=["mcp_server.py"]
            )
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    
                    await session.initialize()
                    tools = await self._build_tools(session)
                    
                    historial = cargar_historial(session_id)
                    
                    
                    if not historial:
                        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                    else:
                        messages = historial
                    
                    messages.append({"role": "user", "content": pregunta})
                    
                    guardar_mensaje(session_id, "user", pregunta)
                    
                    herramientas_usadas = []
                    MAX_ITERACIONES = 10
                    iteracion = 0
                    
                    while True:
                        iteracion += 1
                        if iteracion > MAX_ITERACIONES:
                            respuesta = "No se pudo resolver en el limite de iteraciones."
                            guardar_mensaje(session_id, "assistant", respuesta)
                            return respuesta, herramientas_usadas
                        
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            tools=tools,
                        )
                        
                        message = response.choices[0].message
                        
                        if not message.tool_calls:
                            guardar_mensaje(session_id, "assistant", message.content)
                            return message.content, herramientas_usadas
                        
                        messages.append(message)
                        
                        for tool_call in message.tool_calls:
                            nombre = tool_call.function.name
                            arguments = json.loads(tool_call.function.arguments)
                            
                            print(f"[agente] usando herramienta : {nombre} ({arguments})")
                            
                            resultado = await session.call_tool(nombre, arguments)
                            
                            if nombre not in herramientas_usadas:
                                herramientas_usadas.append(nombre)
                                
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": str(resultado),
                                })
                            
                            
        async def _build_tools(self, session: ClientSession) -> list[dict]:
            """
            Convierte las herramientas registradas en el servidor MCP al formato que entiende la API de Ollama.
            """
            mcp_tools = await session.list_tools()
            tools = []
            
            for tool in mcp_tools.tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema,
                    }
                })
            return tools
            
            
                            