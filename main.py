import httpx
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from datetime import date
from fastmcp import FastMCP
from fastmcp.tools import ToolManager, FunctionTool
import asyncio
import os

# --- 1. CONFIGURAÇÃO ---
VECTOR_API_URL = os.getenv("VECTOR_API_URL")

# --- 2. MODELOS DE INPUT (Nenhuma alteração aqui) ---
class AdicionarAtletaInput(BaseModel):
    name: str = Field(..., description="Nome completo do atleta.")
    birth_date: date = Field(..., description="Data de nascimento no formato AAAA-MM-DD.")
    sport: str = Field(..., description="Modalidade esportiva principal do atleta.")
    details: Dict[str, Any] = Field({}, description="Dicionário com detalhes adicionais como peso, altura, etc. Ex: {'weight_kg': 75.5, 'height_cm': 180}")

class AtletaInput(BaseModel):
    nome: str = Field(..., description="Nome do atleta para buscar, atualizar ou deletar.")

class AtualizarAtletaInput(BaseModel):
    nome_original: str = Field(..., description="Nome atual do atleta que será atualizado.")
    novos_dados: Dict[str, Any] = Field(..., description="Dicionário com os novos dados para o atleta.")

class CompararBenchmarkInput(BaseModel):
    nome_atleta: str = Field(..., description="Nome do atleta a ser comparado.")
    nome_teste: str = Field(..., description="Nome do teste para comparação (ex: 'CMJ').")

class RegistrarTreinoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta que realizou o treino.")
    details: str = Field(..., description="Descrição completa dos exercícios, séries, repetições e cargas.")
    rpe: int = Field(..., description="Percepção Subjetiva de Esforço, em uma escala de 1 a 10.")
    duration_minutes: int = Field(..., description="Duração total da sessão de treino em minutos.")

class RegistrarAvaliacaoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta que foi avaliado.")
    assessment_type: str = Field(..., description="Tipo de teste realizado. Ex: 'RAST', 'Y_BALANCE', 'CMJ'.")
    results: Dict[str, Any] = Field(..., description="Dicionário com os resultados do teste. Ex: {'melhor_tempo_s': 4.1, 'pior_tempo_s': 4.8}")

class RegistrarBemEstarInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta.")
    qualidade_sono: int = Field(..., ge=1, le=10, description="Qualidade do sono (1 a 10).")
    nivel_estresse: int = Field(..., ge=1, le=10, description="Nível de estresse (1 a 10).")
    nivel_fadiga: int = Field(..., ge=1, le=10, description="Nível de fadiga (1 a 10).")
    dores_musculares: str = Field("Nenhuma", description="Descrição de dores musculares.")

class GerarMesocicloInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta para o qual o plano será gerado.")
    objective: str = Field(..., description="Objetivo principal do mesociclo. Ex: 'hipertrofia', 'força máxima'.")
    duration_weeks: int = Field(..., description="Número de semanas que o mesociclo durará.")
    sessions_per_week: int = Field(..., description="Número de sessões de treino por semana.")
    progression_model: str = Field(..., description="Modelo de progressão de carga. Ex: 'linear', 'ondulatoria'.")

class RelatorioAtletaInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta.")

class GraficoInput(BaseModel):
    athlete_id: int = Field(..., description="ID numérico do atleta.")
    metric_name: str = Field(..., description="Nome da métrica para gerar o gráfico (ex: 'acwr', 'strain', 'monotony').")

# --- 3. FUNÇÕES-FERRAMENTA (Nenhuma alteração aqui) ---
async def _call_api(method: str, endpoint: str, json_data: dict = None, params: dict = None) -> Dict[str, Any]:
    """Função auxiliar para fazer chamadas HTTP e tratar respostas."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(method, f"{VECTOR_API_URL}{endpoint}", json=json_data, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"status": "erro", "detalhe": e.response.json()}
        except Exception as e:
            return {"status": "erro_geral", "detalhe": str(e)}

async def adicionar_atleta(params: AdicionarAtletaInput) -> Dict[str, Any]:
    """Cadastra um novo atleta no sistema."""
    return await _call_api("POST", "/athletes/", json_data=params.model_dump(mode='json'))

async def listar_atletas() -> List[Dict[str, Any]]:
    """Retorna uma lista de todos os atletas cadastrados."""
    return await _call_api("GET", "/athletes/")

async def buscar_atleta_pelo_nome(params: AtletaInput) -> Dict[str, Any]:
    """Busca os detalhes de um atleta específico pelo nome."""
    return await _call_api("GET", f"/athletes/{params.nome}")

async def deletar_atleta(params: AtletaInput) -> Dict[str, Any]:
    """Deleta um atleta do sistema pelo nome."""
    atleta_dados = await buscar_atleta_pelo_nome(params)
    if atleta_dados and atleta_dados.get("id"):
        return await _call_api("DELETE", f"/athletes/{atleta_dados['id']}")
    return atleta_dados

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

# --- 4. CONFIGURAÇÃO DO GERENCIADOR DE FERRAMENTAS (SEÇÃO CORRIGIDA) ---
tool_manager = ToolManager()

# Registrando todas as funções com o schema dos parâmetros em formato de dicionário
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

# --- 5. CRIAÇÃO DO SERVIDOR MCP ---

# Usamos asyncio.run() para executar a função assíncrona 'get_tools' e obter a lista.
tools_list = asyncio.run(tool_manager.get_tools())

# Agora passamos a lista resolvida para o servidor.
app = FastMCP(
    tools=tool_manager.get_tools() # <-- CORREÇÃO FINAL: Usamos o método get_tools() para obter a lista.
)

print("Servidor de Ferramentas VECTOR AI (Cliente HTTP) configurado e pronto.")
print("Execute com: uvicorn main:app --reload --port 8001")
