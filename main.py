import httpx
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import date
from fastmcp import FastMCP
from fastmcp.tools import ToolManager, FunctionTool
import os
import logging
import asyncio

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. CONFIGURAÇÃO ---
VECTOR_API_URL = os.getenv("VECTOR_API_URL")
if not VECTOR_API_URL:
    raise ValueError("VECTOR_API_URL environment variable is required")

# Remover barra final se existir
VECTOR_API_URL = VECTOR_API_URL.rstrip('/')

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
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            try:
                error_detail = e.response.json()
            except Exception:
                error_detail = e.response.text
            return {"status": "erro", "codigo": e.response.status_code, "detalhe": error_detail}
            
        except httpx.TimeoutException:
            logger.error("Request timeout")
            return {"status": "erro_timeout", "detalhe": "A requisição excedeu o tempo limite"}
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {"status": "erro_geral", "detalhe": str(e)}

async def adicionar_atleta(params: AdicionarAtletaInput) -> Dict[str, Any]:
    """Cadastra um novo atleta no sistema."""
    return await _call_api("POST", "/athletes/", json_data=params.model_dump(mode='json'))

async def listar_atletas() -> Dict[str, Any]:  # Mudei o tipo de retorno para consistência
    """Retorna uma lista de todos os atletas cadastrados."""
    return await _call_api("GET", "/athletes/")

async def buscar_atleta_pelo_nome(params: AtletaInput) -> Dict[str, Any]:
    """Busca os detalhes de um atleta específico pelo nome."""
    return await _call_api("GET", f"/athletes/{params.nome}")

async def deletar_atleta(params: AtletaInput) -> Dict[str, Any]:
    """Deleta um atleta do sistema pelo nome."""
    # Primeiro busca o atleta
    atleta_dados = await buscar_atleta_pelo_nome(params)
    
    # Verifica se houve erro na busca
    if atleta_dados.get("status") == "erro":
        return atleta_dados
    
    # Verifica se encontrou o atleta e tem ID
    athlete_id = atleta_dados.get("id")
    if not athlete_id:
        return {
            "status": "erro", 
            "detalhe": f"Atleta '{params.nome}' não encontrado ou não possui ID válido"
        }
    
    # Deleta o atleta usando o ID
    return await _call_api("DELETE", f"/athletes/{athlete_id}")

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
tool_manager = ToolManager()

# Registrando todas as funções com o schema dos parâmetros
tool_manager.add_tool(FunctionTool(name="adicionar_atleta", fn=adicionar_atleta, parameters=AdicionarAtletaInput.model_json_schema()))
tool_manager.add_tool(FunctionTool(name="listar_atletas", fn=listar_atletas, parameters={}))
tool_manager.add_tool(FunctionTool(name="buscar_atleta_pelo_nome", fn=buscar_atleta_pelo_nome, parameters=AtletaInput.model_json_schema()))
tool_manager.add_tool(FunctionTool(name="deletar_atleta", fn=deletar_atleta, parameters=AtletaInput.model_json_schema()))
tool_manager.add_tool(FunctionTool(name="registrar_treino", fn=registrar_treino, parameters=RegistrarTreinoInput.model_json_schema()))
tool_manager.add_tool(FunctionTool(name="registrar_avaliacao", fn=registrar_avaliacao, parameters=RegistrarAvaliacaoInput.model_json_schema()))
tool_manager.add_tool(FunctionTool(name="registrar_bem_estar", fn=registrar_bem_estar, parameters=RegistrarBemEstarInput.model_json_schema()))
tool_manager.add_tool(FunctionTool(name="gerar_mesociclo", fn=gerar_mesociclo, parameters=GerarMesocicloInput.model_json_schema()))
tool_manager.add_tool(FunctionTool(name="gerar_relatorio_atleta", fn=gerar_relatorio_atleta, parameters=RelatorioAtletaInput.model_json_schema()))
tool_manager.add_tool(FunctionTool(name="gerar_relatorio_equipe", fn=gerar_relatorio_equipe, parameters={}))
tool_manager.add_tool(FunctionTool(name="gerar_grafico_performance", fn=gerar_grafico_performance, parameters=GraficoInput.model_json_schema()))

# --- 5. CRIAÇÃO DO SERVIDOR MCP (CORRIGIDO) --

async def init_server():
    """Inicializa o servidor MCP de forma assíncrona."""
    try:
        tools = await tool_manager.get_tools()
        app = FastMCP(tools=tools)
        logger.info("Servidor MCP inicializado com sucesso")
        return app
    except Exception as e:
        logger.error(f"Erro ao inicializar servidor MCP: {e}")
        raise

# Inicializa o servidor de forma síncrona
app = asyncio.run(init_server())

print("Servidor de Ferramentas VECTOR AI (Cliente HTTP) configurado e pronto.")
print("Execute com: uvicorn main:app --reload --port 8001")
