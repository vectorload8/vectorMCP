import httpx
import asyncio
import json
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import date
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import logging
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração da API
VECTOR_API_URL = os.getenv("VECTOR_API_URL", "https://vectorapi.up.railway.app/v1")
VECTOR_API_URL = VECTOR_API_URL.rstrip('/')

# Modelos de Input (mantendo os mesmos do seu código)
class AdicionarAtletaInput(BaseModel):
    name: str = Field(..., description="Nome completo do atleta.", min_length=1)
    birth_date: date = Field(..., description="Data de nascimento no formato AAAA-MM-DD.")
    sport: str = Field(..., description="Modalidade esportiva principal do atleta.", min_length=1)
    details: Dict[str, Any] = Field({}, description="Dicionário com detalhes adicionais como peso, altura, etc.")

class AtletaInput(BaseModel):
    nome: str = Field(..., description="Nome do atleta para buscar, atualizar ou deletar.", min_length=1)

class RegistrarTreinoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta que realizou o treino.", gt=0)
    details: str = Field(..., description="Descrição completa dos exercícios, séries, repetições e cargas.", min_length=1)
    rpe: int = Field(..., description="Percepção Subjetiva de Esforço, em uma escala de 1 a 10.", ge=1, le=10)
    duration_minutes: int = Field(..., description="Duração total da sessão de treino em minutos.", gt=0)

class RegistrarAvaliacaoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta que foi avaliado.", gt=0)
    assessment_type: str = Field(..., description="Tipo de teste realizado. Ex: 'RAST', 'Y_BALANCE', 'CMJ'.", min_length=1)
    results: Dict[str, Any] = Field(..., description="Dicionário com os resultados do teste.")

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
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"API call error: {str(e)}")
            return {"status": "erro", "detalhe": str(e)}

# Criar o servidor MCP
server = Server("vector-ai-sports")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Lista todas as ferramentas disponíveis."""
    return [
        types.Tool(
            name="adicionar_atleta",
            description="Cadastra um novo atleta no sistema",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome completo do atleta"},
                    "birth_date": {"type": "string", "format": "date", "description": "Data de nascimento (AAAA-MM-DD)"},
                    "sport": {"type": "string", "description": "Modalidade esportiva principal"},
                    "details": {"type": "object", "description": "Detalhes adicionais (peso, altura, etc.)"}
                },
                "required": ["name", "birth_date", "sport"]
            },
        ),
        types.Tool(
            name="listar_atletas",
            description="Retorna uma lista de todos os atletas cadastrados",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="buscar_atleta_pelo_nome",
            description="Busca os detalhes de um atleta específico pelo nome",
            inputSchema={
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do atleta para buscar"}
                },
                "required": ["nome"]
            },
        ),
        types.Tool(
            name="deletar_atleta",
            description="Deleta um atleta do sistema pelo nome",
            inputSchema={
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do atleta para deletar"}
                },
                "required": ["nome"]
            },
        ),
        types.Tool(
            name="registrar_treino",
            description="Registra uma nova sessão de treino para um atleta",
            inputSchema={
                "type": "object",
                "properties": {
                    "athlete_id": {"type": "integer", "description": "ID numérico do atleta"},
                    "details": {"type": "string", "description": "Descrição completa do treino"},
                    "rpe": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Percepção de esforço (1-10)"},
                    "duration_minutes": {"type": "integer", "description": "Duração em minutos"}
                },
                "required": ["athlete_id", "details", "rpe", "duration_minutes"]
            },
        ),
        types.Tool(
            name="registrar_avaliacao",
            description="Registra os resultados de uma avaliação de performance",
            inputSchema={
                "type": "object",
                "properties": {
                    "athlete_id": {"type": "integer", "description": "ID numérico do atleta"},
                    "assessment_type": {"type": "string", "description": "Tipo de teste (ex: 'CMJ', 'RAST')"},
                    "results": {"type": "object", "description": "Resultados do teste"}
                },
                "required": ["athlete_id", "assessment_type", "results"]
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Executa uma ferramenta com os argumentos fornecidos."""
    try:
        logger.info(f"Tool called: {name} with arguments: {arguments}")
        
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
                    result = {"status": "erro", "detalhe": "Atleta não encontrado"}
        elif name == "registrar_treino":
            result = await _call_api("POST", "/workouts/register", json_data=arguments)
        elif name == "registrar_avaliacao":
            result = await _call_api("POST", "/assessments/", json_data=arguments)
        else:
            result = {"status": "erro", "detalhe": f"Ferramenta '{name}' não reconhecida"}
        
        # Converter resultado para texto
        response_text = json.dumps(result, indent=2, ensure_ascii=False)
        return [types.TextContent(type="text", text=response_text)]
        
    except Exception as e:
        logger.error(f"Error in handle_call_tool: {str(e)}")
        error_response = {"status": "erro", "detalhe": str(e)}
        return [types.TextContent(type="text", text=json.dumps(error_response, indent=2))]

async def main():
    # Importar o módulo de transporte stdio
    from mcp.server.stdio import stdio_server
    
    logger.info("Starting Vector AI MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="vector-ai-sports",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
