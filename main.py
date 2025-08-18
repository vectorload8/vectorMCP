from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import json
import httpx
import asyncio
import logging
from typing import Dict, Any
import os

# Configuração
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VECTOR_API_URL = os.getenv("VECTOR_API_URL", "https://vectorapi.up.railway.app/v1").rstrip('/')

app = FastAPI(title="Vector AI MCP Bridge", version="1.0.0")

# Função auxiliar para API calls
async def _call_api(method: str, endpoint: str, json_data: dict = None) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        try:
            url = f"{VECTOR_API_URL}{endpoint}"
            response = await client.request(method, url, json=json_data, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API error: {str(e)}")
            return {"status": "erro", "detalhe": str(e)}

# Definição das ferramentas MCP
MCP_TOOLS = [
    {
        "name": "adicionar_atleta",
        "description": "Cadastra um novo atleta no sistema",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome completo do atleta"},
                "birth_date": {"type": "string", "format": "date", "description": "Data de nascimento (AAAA-MM-DD)"},
                "sport": {"type": "string", "description": "Modalidade esportiva principal"},
                "details": {"type": "object", "description": "Detalhes adicionais"}
            },
            "required": ["name", "birth_date", "sport"]
        }
    },
    {
        "name": "listar_atletas",
        "description": "Lista todos os atletas cadastrados",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "buscar_atleta_pelo_nome",
        "description": "Busca atleta por nome",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome do atleta"}
            },
            "required": ["nome"]
        }
    },
    {
        "name": "registrar_treino",
        "description": "Registra sessão de treino",
        "inputSchema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "integer", "description": "ID do atleta"},
                "details": {"type": "string", "description": "Detalhes do treino"},
                "rpe": {"type": "integer", "minimum": 1, "maximum": 10, "description": "RPE (1-10)"},
                "duration_minutes": {"type": "integer", "description": "Duração em minutos"}
            },
            "required": ["athlete_id", "details", "rpe", "duration_minutes"]
        }
    }
]

# Executar ferramentas
async def execute_tool(name: str, arguments: dict) -> dict:
    try:
        if name == "adicionar_atleta":
            return await _call_api("POST", "/athletes/", json_data=arguments)
        elif name == "listar_atletas":
            return await _call_api("GET", "/athletes/")
        elif name == "buscar_atleta_pelo_nome":
            nome = arguments.get("nome")
            return await _call_api("GET", f"/athletes/{nome}")
        elif name == "registrar_treino":
            return await _call_api("POST", "/workouts/register", json_data=arguments)
        else:
            return {"status": "erro", "detalhe": f"Ferramenta '{name}' não encontrada"}
    except Exception as e:
        return {"status": "erro", "detalhe": str(e)}

# WebSocket endpoint para MCP
@app.websocket("/mcp")
async def websocket_mcp_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket MCP connection established")
    
    try:
        # Enviar inicialização
        init_response = {
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False}
                },
                "serverInfo": {
                    "name": "vector-ai-sports",
                    "version": "1.0.0"
                }
            }
        }
        
        while True:
            # Receber mensagem MCP
            message = await websocket.receive_json()
            logger.info(f"Received MCP message: {message}")
            
            # Processar diferentes tipos de requisições MCP
            if message.get("method") == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {"tools": MCP_TOOLS}
                }
                
            elif message.get("method") == "tools/call":
                params = message.get("params", {})
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                result = await execute_tool(tool_name, arguments)
                
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2, ensure_ascii=False)
                            }
                        ]
                    }
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32601, "message": "Method not found"}
                }
            
            await websocket.send_json(response)
            
    except WebSocketDisconnect:
        logger.info("WebSocket MCP connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")

# HTTP endpoints para debug
@app.get("/")
async def root():
    return JSONResponse({
        "message": "Vector AI MCP Bridge Server",
        "version": "1.0.0",
        "mcp_endpoint": "/mcp (WebSocket)",
        "tools_count": len(MCP_TOOLS)
    })

@app.get("/tools")
async def list_tools():
    return JSONResponse({"tools": MCP_TOOLS})

@app.get("/health")
async def health():
    return JSONResponse({"status": "healthy"})

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
