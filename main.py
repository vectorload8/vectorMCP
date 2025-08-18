import httpx
import json
import logging
import os
import asyncio
from datetime import date
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração da API
VECTOR_API_URL = os.getenv("VECTOR_API_URL", "https://vectorapi.up.railway.app/v1")
VECTOR_API_URL = VECTOR_API_URL.rstrip('/')

# Modelos Pydantic (mantendo os originais)
class AdicionarAtletaInput(BaseModel):
    name: str = Field(..., description="Nome completo do atleta.", min_length=1)
    birth_date: date = Field(..., description="Data de nascimento no formato AAAA-MM-DD.")
    sport: str = Field(..., description="Modalidade esportiva principal do atleta.", min_length=1)
    details: Dict[str, Any] = Field({}, description="Dicionário com detalhes adicionais")

class AtletaInput(BaseModel):
    nome: str = Field(..., description="Nome do atleta", min_length=1)

class RegistrarTreinoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta", gt=0)
    details: str = Field(..., description="Descrição completa do treino", min_length=1)
    rpe: int = Field(..., description="Percepção de esforço (1-10)", ge=1, le=10)
    duration_minutes: int = Field(..., description="Duração em minutos", gt=0)

class RegistrarAvaliacaoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta", gt=0)
    assessment_type: str = Field(..., description="Tipo de teste", min_length=1)
    results: Dict[str, Any] = Field(..., description="Resultados do teste")

class RegistrarBemEstarInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta", gt=0)
    qualidade_sono: int = Field(..., ge=1, le=10, description="Qualidade do sono (1-10)")
    nivel_estresse: int = Field(..., ge=1, le=10, description="Nível de estresse (1-10)")
    nivel_fadiga: int = Field(..., ge=1, le=10, description="Nível de fadiga (1-10)")
    dores_musculares: str = Field("Nenhuma", description="Descrição de dores musculares")

class GerarMesocicloInput(BaseModel):
    athlete_id: int = Field(..., description="ID do atleta", gt=0)
    objective: str = Field(..., description="Objetivo do mesociclo", min_length=1)
    duration_weeks: int = Field(..., description="Duração em semanas", gt=0, le=52)
    sessions_per_week: int = Field(..., description="Sessões por semana", gt=0, le=14)
    progression_model: str = Field(..., description="Modelo de progressão", min_length=1)

class RelatorioAtletaInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta", gt=0)

class GraficoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta", gt=0)
    metric_name: str = Field(..., description="Nome da métrica", min_length=1)

# Função auxiliar para chamadas da API
async def _call_api(method: str, endpoint: str, json_data: dict = None, params: dict = None) -> Dict[str, Any]:
    """Função auxiliar para fazer chamadas HTTP e tratar respostas."""
    async with httpx.AsyncClient() as client:
        try:
            url = f"{VECTOR_API_URL}{endpoint}"
            logger.info(f"Making {method} request to {url}")
            
            response = await client.request(
                method, 
                url, 
                json=json_data, 
                params=params, 
                timeout=15.0
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"API call successful: {method} {endpoint}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            try:
                error_detail = e.response.json()
            except:
                error_detail = e.response.text
            return {"status": "erro", "codigo": e.response.status_code, "detalhe": error_detail}
            
        except Exception as e:
            logger.error(f"API call error: {str(e)}")
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
                "details": {"type": "object", "description": "Detalhes adicionais como peso, altura, etc.", "default": {}}
            },
            "required": ["name", "birth_date", "sport"]
        }
    },
    {
        "name": "listar_atletas",
        "description": "Retorna uma lista de todos os atletas cadastrados",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "buscar_atleta_pelo_nome",
        "description": "Busca os detalhes de um atleta específico pelo nome",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome do atleta para buscar"}
            },
            "required": ["nome"]
        }
    },
    {
        "name": "deletar_atleta",
        "description": "Deleta um atleta do sistema pelo nome",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome do atleta para deletar"}
            },
            "required": ["nome"]
        }
    },
    {
        "name": "registrar_treino",
        "description": "Registra uma nova sessão de treino para um atleta",
        "inputSchema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "integer", "description": "ID numérico do atleta"},
                "details": {"type": "string", "description": "Descrição completa dos exercícios, séries, repetições e cargas"},
                "rpe": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Percepção Subjetiva de Esforço (1-10)"},
                "duration_minutes": {"type": "integer", "minimum": 1, "description": "Duração total da sessão em minutos"}
            },
            "required": ["athlete_id", "details", "rpe", "duration_minutes"]
        }
    },
    {
        "name": "registrar_avaliacao",
        "description": "Registra os resultados de uma avaliação de performance formal",
        "inputSchema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "integer", "description": "ID numérico do atleta"},
                "assessment_type": {"type": "string", "description": "Tipo de teste (ex: 'RAST', 'Y_BALANCE', 'CMJ')"},
                "results": {"type": "object", "description": "Dicionário com os resultados do teste"}
            },
            "required": ["athlete_id", "assessment_type", "results"]
        }
    },
    {
        "name": "registrar_bem_estar",
        "description": "Registra o estado de bem-estar diário de um atleta",
        "inputSchema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "integer", "description": "ID numérico do atleta"},
                "qualidade_sono": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Qualidade do sono (1-10)"},
                "nivel_estresse": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Nível de estresse (1-10)"},
                "nivel_fadiga": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Nível de fadiga (1-10)"},
                "dores_musculares": {"type": "string", "description": "Descrição de dores musculares", "default": "Nenhuma"}
            },
            "required": ["athlete_id", "qualidade_sono", "nivel_estresse", "nivel_fadiga"]
        }
    },
    {
        "name": "gerar_mesociclo",
        "description": "Cria um plano de treino estruturado (mesociclo) para um atleta",
        "inputSchema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "integer", "description": "ID do atleta para o qual o plano será gerado"},
                "objective": {"type": "string", "description": "Objetivo principal (ex: 'hipertrofia', 'força máxima')"},
                "duration_weeks": {"type": "integer", "minimum": 1, "maximum": 52, "description": "Número de semanas do mesociclo"},
                "sessions_per_week": {"type": "integer", "minimum": 1, "maximum": 14, "description": "Sessões por semana"},
                "progression_model": {"type": "string", "description": "Modelo de progressão (ex: 'linear', 'ondulatoria')"}
            },
            "required": ["athlete_id", "objective", "duration_weeks", "sessions_per_week", "progression_model"]
        }
    },
    {
        "name": "gerar_relatorio_atleta",
        "description": "Gera um relatório de performance completo para um atleta específico",
        "inputSchema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "integer", "description": "ID numérico do atleta"}
            },
            "required": ["athlete_id"]
        }
    },
    {
        "name": "gerar_relatorio_equipe",
        "description": "Gera um relatório resumido com o status de todos os atletas da equipe",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "gerar_grafico_performance",
        "description": "Gera um link para uma imagem de gráfico de performance para um atleta e uma métrica",
        "inputSchema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "integer", "description": "ID numérico do atleta"},
                "metric_name": {"type": "string", "description": "Nome da métrica (ex: 'acwr', 'strain', 'monotony')"}
            },
            "required": ["athlete_id", "metric_name"]
        }
    }
]

# Executar ferramentas
async def execute_tool(name: str, arguments: dict) -> dict:
    """Executa uma ferramenta específica com os argumentos fornecidos."""
    try:
        logger.info(f"Executing tool: {name} with arguments: {arguments}")
        
        if name == "adicionar_atleta":
            result = await _call_api("POST", "/athletes/", json_data=arguments)
        elif name == "listar_atletas":
            result = await _call_api("GET", "/athletes/")
        elif name == "buscar_atleta_pelo_nome":
            nome = arguments.get("nome")
            result = await _call_api("GET", f"/athletes/{nome}")
        elif name == "deletar_atleta":
            nome = arguments.get("nome")
            # Primeiro busca o atleta para obter o ID
            atleta_dados = await _call_api("GET", f"/athletes/{nome}")
            if atleta_dados.get("status") == "erro":
                result = atleta_dados
            else:
                athlete_id = atleta_dados.get("id")
                if athlete_id:
                    result = await _call_api("DELETE", f"/athletes/{athlete_id}")
                else:
                    result = {"status": "erro", "detalhe": "Atleta não encontrado ou sem ID válido"}
        elif name == "registrar_treino":
            result = await _call_api("POST", "/workouts/register", json_data=arguments)
        elif name == "registrar_avaliacao":
            result = await _call_api("POST", "/assessments/", json_data=arguments)
        elif name == "registrar_bem_estar":
            result = await _call_api("POST", "/wellness/log", json_data=arguments)
        elif name == "gerar_mesociclo":
            result = await _call_api("POST", "/planning/generate-mesocycle", json_data=arguments)
        elif name == "gerar_relatorio_atleta":
            athlete_id = arguments.get("athlete_id")
            result = await _call_api("GET", f"/reports/athlete-report/{athlete_id}")
        elif name == "gerar_relatorio_equipe":
            result = await _call_api("GET", "/reports/team-report")
        elif name == "gerar_grafico_performance":
            result = await _call_api("GET", "/charts/performance-chart", params=arguments)
        else:
            result = {"status": "erro", "detalhe": f"Ferramenta '{name}' não reconhecida"}
        
        logger.info(f"Tool execution completed: {name}")
        return result
        
    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}")
        return {"status": "erro", "detalhe": str(e)}

# Criar aplicação FastAPI
app = FastAPI(
    title="Vector AI MCP Server",
    description="Servidor MCP para Vector AI Sports Platform",
    version="1.0.0"
)

# Adicionar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint WebSocket para MCP
@app.websocket("/mcp")
async def websocket_mcp_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("New MCP WebSocket connection established")
    
    try:
        while True:
            # Receber mensagem JSON-RPC
            message = await websocket.receive_json()
            logger.info(f"Received MCP message: {message.get('method', 'unknown')} (id: {message.get('id', 'none')})")
            
            # Processar mensagem MCP
            if message.get("method") == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
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
                
            elif message.get("method") == "tools/list":
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
                                "text": json.dumps(result, indent=2, ensure_ascii=False, default=str)
                            }
                        ]
                    }
                }
                
            elif message.get("method") == "notifications/initialized":
                # Apenas confirmar inicialização
                continue
                
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {message.get('method')}"
                    }
                }
            
            await websocket.send_json(response)
            logger.debug(f"Sent response for {message.get('method', 'unknown')}")
            
    except WebSocketDisconnect:
        logger.info("MCP WebSocket connection closed normally")
    except Exception as e:
        logger.error(f"MCP WebSocket error: {str(e)}", exc_info=True)

# Endpoints HTTP para debug e health checks
@app.get("/")
async def root():
    return JSONResponse({
        "message": "Vector AI MCP Server está rodando",
        "version": "1.0.0",
        "mcp_endpoint": "/mcp (WebSocket)",
        "tools_count": len(MCP_TOOLS),
        "vector_api_url": VECTOR_API_URL,
        "status": "online"
    })

@app.get("/health")
async def health_check():
    try:
        # Testar conectividade com a API Vector
        result = await _call_api("GET", "/health")
        api_status = "ok" if result.get("status") != "erro" else "error"
    except:
        api_status = "unknown"
    
    return JSONResponse({
        "status": "healthy",
        "mcp_server": "ready",
        "vector_api": api_status,
        "tools_available": len(MCP_TOOLS)
    })

@app.get("/tools")
async def list_tools():
    """Lista todas as ferramentas disponíveis no servidor MCP"""
    return JSONResponse({
        "tools": MCP_TOOLS,
        "total": len(MCP_TOOLS)
    })

# Endpoint para testar uma ferramenta específica
@app.post("/test-tool/{tool_name}")
async def test_tool(tool_name: str, arguments: dict = None):
    """Endpoint para testar uma ferramenta específica (apenas para debug)"""
    if arguments is None:
        arguments = {}
    
    result = await execute_tool(tool_name, arguments)
    return JSONResponse(result)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting Vector AI MCP Server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info"))
