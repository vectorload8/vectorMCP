import httpx
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import date
from fastmcp import FastMCP
from fastmcp.tools import ToolManager, FunctionTool
import os
import logging

# Configurar logging detalhado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURAÇÃO ---
logger.info("Iniciando configuração do servidor MCP...")

VECTOR_API_URL = os.getenv("VECTOR_API_URL")
logger.info(f"VECTOR_API_URL from environment: {VECTOR_API_URL}")

if not VECTOR_API_URL:
    logger.error("VECTOR_API_URL environment variable is not set")
    raise ValueError("VECTOR_API_URL environment variable is required")

# Remover barra final se existir
VECTOR_API_URL = VECTOR_API_URL.rstrip('/')
logger.info(f"Final VECTOR_API_URL: {VECTOR_API_URL}")
logger.info("Configuração inicial concluída com sucesso")

# --- 2. MODELOS DE INPUT (COM MELHORIAS) ---
class AdicionarAtletaInput(BaseModel):
    name: str = Field(..., description="Nome completo do atleta.", min_length=1)
    birth_date: date = Field(..., description="Data de nascimento no formato AAAA-MM-DD.")
    sport: str = Field(..., description="Modalidade esportiva principal do atleta.", min_length=1)
    details: Dict[str, Any] = Field({}, description="Dicionário com detalhes adicionais como peso, altura, etc. Ex: {'weight_kg': 75.5, 'height_cm': 180}")

class AtletaInput(BaseModel):
    nome: str = Field(..., description="Nome do atleta para buscar, atualizar ou deletar.", min_length=1)

class AtualizarAtletaInput(BaseModel):
    nome_original: str = Field(..., description="Nome atual do atleta que será atualizado.", min_length=1)
    novos_dados: Dict[str, Any] = Field(..., description="Dicionário com os novos dados para o atleta.")

class CompararBenchmarkInput(BaseModel):
    nome_atleta: str = Field(..., description="Nome do atleta a ser comparado.", min_length=1)
    nome_teste: str = Field(..., description="Nome do teste para comparação (ex: 'CMJ').", min_length=1)

class RegistrarTreinoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta que realizou o treino.", gt=0)
    details: str = Field(..., description="Descrição completa dos exercícios, séries, repetições e cargas.", min_length=1)
    rpe: int = Field(..., description="Percepção Subjetiva de Esforço, em uma escala de 1 a 10.", ge=1, le=10)
    duration_minutes: int = Field(..., description="Duração total da sessão de treino em minutos.", gt=0)

class RegistrarAvaliacaoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta que foi avaliado.", gt=0)
    assessment_type: str = Field(..., description="Tipo de teste realizado. Ex: 'RAST', 'Y_BALANCE', 'CMJ'.", min_length=1)
    results: Dict[str, Any] = Field(..., description="Dicionário com os resultados do teste. Ex: {'melhor_tempo_s': 4.1, 'pior_tempo_s': 4.8}")

class RegistrarBemEstarInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta.", gt=0)
    qualidade_sono: int = Field(..., ge=1, le=10, description="Qualidade do sono (1 a 10).")
    nivel_estresse: int = Field(..., ge=1, le=10, description="Nível de estresse (1 a 10).")
    nivel_fadiga: int = Field(..., ge=1, le=10, description="Nível de fadiga (1 a 10).")
    dores_musculares: str = Field("Nenhuma", description="Descrição de dores musculares.")

class GerarMesocicloInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta para o qual o plano será gerado.", gt=0)
    objective: str = Field(..., description="Objetivo principal do mesociclo. Ex: 'hipertrofia', 'força máxima'.", min_length=1)
    duration_weeks: int = Field(..., description="Número de semanas que o mesociclo durará.", gt=0, le=52)
    sessions_per_week: int = Field(..., description="Número de sessões de treino por semana.", gt=0, le=14)
    progression_model: str = Field(..., description="Modelo de progressão de carga. Ex: 'linear', 'ondulatoria'.", min_length=1)

class RelatorioAtletaInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta.", gt=0)

class GraficoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta.", gt=0)
    metric_name: str = Field(..., description="Nome da métrica para gerar o gráfico (ex: 'acwr', 'strain', 'monotony').", min_length=1)

# --- 3. FUNÇÕES-FERRAMENTA (CORRIGIDAS) ---
async def _call_api(method: str, endpoint: str, json_data: dict = None, params: dict = None) -> Dict[str, Any]:
    """Função auxiliar para fazer chamadas HTTP e tratar respostas."""
    logger.debug(f"_call_api called - method: {method}, endpoint: {endpoint}")
    logger.debug(f"json_data: {json_data}")
    logger.debug(f"params: {params}")
    
    async with httpx.AsyncClient() as client:
        try:
            url = f"{VECTOR_API_URL}{endpoint}"
            logger.info(f"Making {method} request to {url}")
            
            response = await client.request(
                method, 
                url, 
                json=json_data, 
                params=params, 
                timeout=10.0  # Timeout reduzido
            )
            logger.info(f"Response status: {response.status_code}")
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"Response data: {result}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            try:
                error_detail = e.response.json()
                logger.debug(f"Error detail (JSON): {error_detail}")
            except Exception as json_error:
                logger.warning(f"Could not parse error response as JSON: {json_error}")
                error_detail = e.response.text
            return {"status": "erro", "codigo": e.response.status_code, "detalhe": error_detail}
            
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {str(e)}")
            return {"status": "erro_timeout", "detalhe": "A requisição excedeu o tempo limite"}
            
        except httpx.RequestError as e:
            logger.error(f"Request error: {str(e)}")
            return {"status": "erro_request", "detalhe": f"Erro na requisição: {str(e)}"}
            
        except Exception as e:
            logger.error(f"Unexpected error in _call_api: {str(e)}", exc_info=True)
            return {"status": "erro_geral", "detalhe": str(e)}

async def adicionar_atleta(params: AdicionarAtletaInput) -> Dict[str, Any]:
    """Cadastra um novo atleta no sistema."""
    logger.info(f"adicionar_atleta called with params: {params}")
    try:
        result = await _call_api("POST", "/athletes/", json_data=params.model_dump(mode='json'))
        logger.info(f"adicionar_atleta result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in adicionar_atleta: {str(e)}", exc_info=True)
        return {"status": "erro_geral", "detalhe": str(e)}

async def listar_atletas() -> Dict[str, Any]:  # Mudei o tipo de retorno para consistência
    """Retorna uma lista de todos os atletas cadastrados."""
    logger.info("listar_atletas called")
    try:
        result = await _call_api("GET", "/athletes/")
        logger.info(f"listar_atletas result count: {len(result) if isinstance(result, list) else 'not a list'}")
        return result
    except Exception as e:
        logger.error(f"Error in listar_atletas: {str(e)}", exc_info=True)
        return {"status": "erro_geral", "detalhe": str(e)}

async def buscar_atleta_pelo_nome(params: AtletaInput) -> Dict[str, Any]:
    """Busca os detalhes de um atleta específico pelo nome."""
    logger.info(f"buscar_atleta_pelo_nome called with params: {params}")
    try:
        result = await _call_api("GET", f"/athletes/{params.nome}")
        logger.info(f"buscar_atleta_pelo_nome result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in buscar_atleta_pelo_nome: {str(e)}", exc_info=True)
        return {"status": "erro_geral", "detalhe": str(e)}

async def deletar_atleta(params: AtletaInput) -> Dict[str, Any]:
    """Deleta um atleta do sistema pelo nome."""
    logger.info(f"deletar_atleta called with params: {params}")
    try:
        # Primeiro busca o atleta
        atleta_dados = await buscar_atleta_pelo_nome(params)
        logger.debug(f"Athlete data found: {atleta_dados}")
        
        # Verifica se houve erro na busca
        if atleta_dados.get("status") == "erro":
            logger.warning(f"Error finding athlete: {atleta_dados}")
            return atleta_dados
        
        # Verifica se encontrou o atleta e tem ID
        athlete_id = atleta_dados.get("id")
        if not athlete_id:
            error_msg = f"Atleta '{params.nome}' não encontrado ou não possui ID válido"
            logger.warning(error_msg)
            return {
                "status": "erro", 
                "detalhe": error_msg
            }
        
        logger.info(f"Deleting athlete with ID: {athlete_id}")
        # Deleta o atleta usando o ID
        result = await _call_api("DELETE", f"/athletes/{athlete_id}")
        logger.info(f"deletar_atleta result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in deletar_atleta: {str(e)}", exc_info=True)
        return {"status": "erro_geral", "detalhe": str(e)}

async def registrar_treino(params: RegistrarTreinoInput) -> Dict[str, Any]:
    """Registra uma nova sessão de treino para um atleta."""
    return await _call_api("POST", "/workouts/register", json_data=params.model_dump(mode='json'))

async def registrar_avaliacao(params: RegistrarAvaliacaoInput) -> Dict[str, Any]:
    """Registra os resultados de uma avaliação de performance formal."""
    return await _call_api("POST", "/assessments/", json_data=params.model_dump(mode='json'))

async def registrar_bem_estar(params: RegistrarBemEstarInput) -> Dict[str, Any]:
    """Registra o estado de bem-estar diário de um atleta."""
    return await _call_api("POST", "/wellness/log", json_data=params.model_dump(mode='json'))

async def gerar_mesociclo(params: GerarMesocicloInput) -> Dict[str, Any]:
    """Cria um plano de treino estruturado (mesociclo) para um atleta."""
    return await _call_api("POST", "/planning/generate-mesocycle", json_data=params.model_dump(mode='json'))

async def gerar_relatorio_atleta(params: RelatorioAtletaInput) -> Dict[str, Any]:
    """Gera um relatório de performance completo para um atleta específico."""
    return await _call_api("GET", f"/reports/athlete-report/{params.athlete_id}")

async def gerar_relatorio_equipe() -> Dict[str, Any]:
    """Gera um relatório resumido com o status de todos os atletas da equipe."""
    return await _call_api("GET", "/reports/team-report")

async def gerar_grafico_performance(params: GraficoInput) -> Dict[str, Any]:
    """Gera um link para uma imagem de gráfico de performance para um atleta e uma métrica."""
    return await _call_api("GET", "/charts/performance-chart", params=params.model_dump(mode='json'))

# --- 4. CONFIGURAÇÃO DO GERENCIADOR DE FERRAMENTAS (CORRIGIDO) ---
logger.info("Configurando gerenciador de ferramentas...")

try:
    tool_manager = ToolManager()
    logger.info("ToolManager criado com sucesso")

    # Registrando todas as funções com o schema dos parâmetros
    tools_to_register = [
        ("adicionar_atleta", adicionar_atleta, AdicionarAtletaInput.model_json_schema()),
        ("listar_atletas", listar_atletas, {}),
        ("buscar_atleta_pelo_nome", buscar_atleta_pelo_nome, AtletaInput.model_json_schema()),
        ("deletar_atleta", deletar_atleta, AtletaInput.model_json_schema()),
        ("registrar_treino", registrar_treino, RegistrarTreinoInput.model_json_schema()),
        ("registrar_avaliacao", registrar_avaliacao, RegistrarAvaliacaoInput.model_json_schema()),
        ("registrar_bem_estar", registrar_bem_estar, RegistrarBemEstarInput.model_json_schema()),
        ("gerar_mesociclo", gerar_mesociclo, GerarMesocicloInput.model_json_schema()),
        ("gerar_relatorio_atleta", gerar_relatorio_atleta, RelatorioAtletaInput.model_json_schema()),
        ("gerar_relatorio_equipe", gerar_relatorio_equipe, {}),
        ("gerar_grafico_performance", gerar_grafico_performance, GraficoInput.model_json_schema()),
    ]

    for tool_name, tool_fn, tool_params in tools_to_register:
        try:
            logger.info(f"Registering tool: {tool_name}")
            tool_manager.add_tool(FunctionTool(name=tool_name, fn=tool_fn, parameters=tool_params))
            logger.debug(f"Tool {tool_name} registered successfully")
        except Exception as e:
            logger.error(f"Failed to register tool {tool_name}: {str(e)}", exc_info=True)
            raise

    logger.info("Todas as ferramentas registradas com sucesso")

except Exception as e:
    logger.error(f"Error setting up tool manager: {str(e)}", exc_info=True)
    raise

# --- 5. CRIAÇÃO DO SERVIDOR MCP (CORRIGIDO) ---
import asyncio

async def init_server():
    """Inicializa o servidor MCP de forma assíncrona."""
    logger.info("Iniciando inicialização do servidor MCP...")
    try:
        logger.info("Obtendo lista de tools do ToolManager...")
        tools = await tool_manager.get_tools()
        logger.info(f"Tools obtidas com sucesso. Quantidade: {len(tools) if tools else 0}")
        logger.debug(f"Tools: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in tools] if tools else 'None'}")
        
        logger.info("Criando instância do FastMCP...")
        app = FastMCP(tools=tools)
        logger.info("Servidor MCP inicializado com sucesso")
        return app
        
    except Exception as e:
        logger.error(f"Erro ao inicializar servidor MCP: {str(e)}", exc_info=True)
        raise

# Função para inicializar de forma síncrona sem conflito com o event loop
def create_app():
    """Cria a aplicação de forma síncrona."""
    logger.info("Executando inicialização do servidor...")
    try:
        # Verifica se já existe um event loop rodando
        try:
            loop = asyncio.get_running_loop()
            logger.info("Event loop já está rodando, usando create_task")
            # Se já existe um loop, criamos uma task
            import concurrent.futures
            import threading
            
            # Executa em uma nova thread para evitar conflito
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, init_server())
                app = future.result()
                logger.info("Servidor inicializado via ThreadPoolExecutor")
                return app
                
        except RuntimeError:
            # Não há event loop rodando, podemos usar asyncio.run
            logger.info("Nenhum event loop detectado, usando asyncio.run")
            app = asyncio.run(init_server())
            logger.info("Servidor inicializado via asyncio.run")
            return app
            
    except Exception as e:
        logger.error(f"Falha crítica na inicialização: {str(e)}", exc_info=True)
        raise

# Inicializa o servidor
app = create_app()

print("🚀 Servidor de Ferramentas VECTOR AI (Cliente HTTP) configurado e pronto.")
print("📋 Execute com: uvicorn main:app --reload --port 8001")
print("📊 Logs detalhados habilitados para debugging")
logger.info("=== SERVIDOR PRONTO PARA CONEXÕES ===")
logger.info("Para testar a conectividade, verifique se VECTOR_API_URL está acessível")
