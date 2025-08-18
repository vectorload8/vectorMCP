# server_fastmcp.py
import os
import json
import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP, Context

# -----------------------------------------------------------------------------
# Config & logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vector-mcp")

VECTOR_API_URL = os.getenv("VECTOR_API_URL", "https://vectorapi.up.railway.app/v1").rstrip("/")

# -----------------------------------------------------------------------------
# HTTP helper
# -----------------------------------------------------------------------------
async def _call_api(
    method: str,
    endpoint: str,
    json_data: Optional[dict] = None,
    params: Optional[dict] = None,
) -> Dict[str, Any]:
    """Chama a Vector API e devolve JSON ou objeto de erro normalizado."""
    url = f"{VECTOR_API_URL}{endpoint}"
    try:
        async with httpx.AsyncClient() as client:
            logger.info("VectorAPI %s %s", method, url)
            resp = await client.request(method, url, json=json_data, params=params, timeout=15.0)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text
        logger.error("VectorAPI HTTP %s -> %s", e.response.status_code, detail)
        return {"status": "erro", "codigo": e.response.status_code, "detalhe": detail}
    except Exception as e:
        logger.exception("VectorAPI error")
        return {"status": "erro", "detalhe": str(e)}

# -----------------------------------------------------------------------------
# FastMCP server (SSE) + Tools
# -----------------------------------------------------------------------------
mcp = FastMCP("vector-ai-sports")

def _to_text(result: Dict[str, Any]) -> str:
    """Converte qualquer payload em string JSON legível pelo cliente MCP."""
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)

# --- 1
@mcp.tool()
async def adicionar_atleta(
    name: str,
    birth_date: str,
    sport: str,
    details: Optional[Dict[str, Any]] = None,
) -> str:
    """Cadastra um novo atleta no sistema."""
    payload = {"name": name, "birth_date": birth_date, "sport": sport, "details": details or {}}
    return _to_text(await _call_api("POST", "/athletes/", json_data=payload))

# --- 2
@mcp.tool()
async def listar_atletas() -> str:
    """Retorna uma lista de todos os atletas cadastrados."""
    return _to_text(await _call_api("GET", "/athletes/"))

# --- 3
@mcp.tool()
async def buscar_atleta_pelo_nome(nome: str) -> str:
    """Busca os detalhes de um atleta específico pelo nome."""
    return _to_text(await _call_api("GET", f"/athletes/{nome}"))

# --- 4
@mcp.tool()
async def deletar_atleta(nome: str) -> str:
    """Deleta um atleta do sistema pelo nome (faz lookup para obter o ID)."""
    atleta = await _call_api("GET", f"/athletes/{nome}")
    if atleta.get("status") == "erro":
        return _to_text(atleta)
    athlete_id = atleta.get("id")
    if not athlete_id:
        return _to_text({"status": "erro", "detalhe": "Atleta não encontrado ou sem ID válido"})
    return _to_text(await _call_api("DELETE", f"/athletes/{athlete_id}"))

# --- 5
@mcp.tool()
async def registrar_treino(
    athlete_id: int,
    details: str,
    rpe: int,
    duration_minutes: int,
) -> str:
    """Registra uma nova sessão de treino para um atleta."""
    payload = {
        "athlete_id": athlete_id,
        "details": details,
        "rpe": rpe,
        "duration_minutes": duration_minutes,
    }
    return _to_text(await _call_api("POST", "/workouts/register", json_data=payload))

# --- 6
@mcp.tool()
async def registrar_avaliacao(
    athlete_id: int,
    assessment_type: str,
    results: Dict[str, Any],
) -> str:
    """Registra os resultados de uma avaliação de performance."""
    payload = {"athlete_id": athlete_id, "assessment_type": assessment_type, "results": results}
    return _to_text(await _call_api("POST", "/assessments/", json_data=payload))

# --- 7
@mcp.tool()
async def registrar_bem_estar(
    athlete_id: int,
    qualidade_sono: int,
    nivel_estresse: int,
    nivel_fadiga: int,
    dores_musculares: str = "Nenhuma",
) -> str:
    """Registra o estado de bem-estar diário de um atleta."""
    payload = {
        "athlete_id": athlete_id,
        "qualidade_sono": qualidade_sono,
        "nivel_estresse": nivel_estresse,
        "nivel_fadiga": nivel_fadiga,
        "dores_musculares": dores_musculares,
    }
    return _to_text(await _call_api("POST", "/wellness/log", json_data=payload))

# --- 8
@mcp.tool()
async def gerar_mesociclo(
    athlete_id: int,
    objective: str,
    duration_weeks: int,
    sessions_per_week: int,
    progression_model: str,
) -> str:
    """Cria um plano de treino estruturado (mesociclo) para um atleta."""
    payload = {
        "athlete_id": athlete_id,
        "objective": objective,
        "duration_weeks": duration_weeks,
        "sessions_per_week": sessions_per_week,
        "progression_model": progression_model,
    }
    return _to_text(await _call_api("POST", "/planning/generate-mesocycle", json_data=payload))

# --- 9
@mcp.tool()
async def gerar_relatorio_atleta(athlete_id: int) -> str:
    """Gera um relatório de performance completo para um atleta específico."""
    return _to_text(await _call_api("GET", f"/reports/athlete-report/{athlete_id}"))

# --- 10
@mcp.tool()
async def gerar_relatorio_equipe() -> str:
    """Gera um relatório resumido com o status de todos os atletas da equipe."""
    return _to_text(await _call_api("GET", "/reports/team-report"))

# --- 11
@mcp.tool()
async def gerar_grafico_performance(athlete_id: int, metric_name: str) -> str:
    """Gera um link para uma imagem de gráfico de performance de um atleta para uma métrica."""
    params = {"athlete_id": athlete_id, "metric_name": metric_name}
    return _to_text(await _call_api("GET", "/charts/performance-chart", params=params))

# -----------------------------------------------------------------------------
# FastAPI app (montando o SSE do MCP em /mcp)
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Vector AI MCP Server",
    description="Servidor MCP (SSE) para Vector AI Sports Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monte o servidor SSE do MCP no caminho /mcp
app.mount("/mcp", mcp.sse_app())

# HTTP endpoints auxiliares
TOOL_NAMES = [
    "adicionar_atleta",
    "listar_atletas",
    "buscar_atleta_pelo_nome",
    "deletar_atleta",
    "registrar_treino",
    "registrar_avaliacao",
    "registrar_bem_estar",
    "gerar_mesociclo",
    "gerar_relatorio_atleta",
    "gerar_relatorio_equipe",
    "gerar_grafico_performance",
]

@app.get("/")
async def root():
    return JSONResponse({
        "message": "Vector AI MCP Server está rodando",
        "version": "1.0.0",
        "mcp_endpoint": "/mcp (SSE)",
        "tools_count": len(TOOL_NAMES),
        "vector_api_url": VECTOR_API_URL,
        "status": "online",
    })

@app.get("/health")
async def health_check():
    try:
        result = await _call_api("GET", "/health")
        api_status = "ok" if result.get("status") != "erro" else "error"
    except Exception:
        api_status = "unknown"
    return JSONResponse({
        "status": "healthy",
        "mcp_server": "ready",
        "vector_api": api_status,
        "tools_available": len(TOOL_NAMES),
    })

@app.get("/tools")
async def list_tools():
    return JSONResponse({"tools": TOOL_NAMES, "total": len(TOOL_NAMES)})

# Execução local (Railway usa PORT)
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    logger.info("Starting Vector AI MCP Server on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
