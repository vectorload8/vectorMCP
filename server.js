import express from "express";
import { createMcpServer } from "@pipedream/mcp";
import axios from "axios";

const VECTOR_API_URL = process.env.VECTOR_API_URL || "https://vectorapi.up.railway.app/v1";

async function callApi(method, endpoint, data = {}, params = {}) {
  try {
    const res = await axios({
      method,
      url: `${VECTOR_API_URL}${endpoint}`,
      data,
      params
    });
    return res.data;
  } catch (err) {
    return {
      status: "erro",
      codigo: err.response?.status,
      detalhe: err.response?.data || err.message
    };
  }
}

const tools = [
  {
    name: "adicionar_atleta",
    description: "Cadastra um novo atleta",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string" },
        birth_date: { type: "string", format: "date" },
        sport: { type: "string" },
        details: { type: "object", default: {} }
      },
      required: ["name", "birth_date", "sport"]
    },
    handler: (args) => callApi("POST", "/athletes/", args)
  },
  {
    name: "listar_atletas",
    description: "Lista atletas cadastrados",
    inputSchema: { type: "object", properties: {} },
    handler: () => callApi("GET", "/athletes/")
  },
  {
    name: "buscar_atleta_pelo_nome",
    description: "Busca atleta pelo nome",
    inputSchema: {
      type: "object",
      properties: { nome: { type: "string" } },
      required: ["nome"]
    },
    handler: ({ nome }) => callApi("GET", `/athletes/${nome}`)
  },
  {
    name: "deletar_atleta",
    description: "Deleta atleta pelo nome",
    inputSchema: {
      type: "object",
      properties: { nome: { type: "string" } },
      required: ["nome"]
    },
    handler: async ({ nome }) => {
      const atleta = await callApi("GET", `/athletes/${nome}`);
      if (atleta?.id) return callApi("DELETE", `/athletes/${atleta.id}`);
      return { status: "erro", detalhe: "Atleta não encontrado" };
    }
  },
  {
    name: "registrar_treino",
    description: "Registra treino",
    inputSchema: {
      type: "object",
      properties: {
        athlete_id: { type: "integer" },
        details: { type: "string" },
        rpe: { type: "integer", minimum: 1, maximum: 10 },
        duration_minutes: { type: "integer", minimum: 1 }
      },
      required: ["athlete_id", "details", "rpe", "duration_minutes"]
    },
    handler: (args) => callApi("POST", "/workouts/register", args)
  },
  {
    name: "registrar_avaliacao",
    description: "Registra avaliação",
    inputSchema: {
      type: "object",
      properties: {
        athlete_id: { type: "integer" },
        assessment_type: { type: "string" },
        results: { type: "object" }
      },
      required: ["athlete_id", "assessment_type", "results"]
    },
    handler: (args) => callApi("POST", "/assessments/", args)
  },
  {
    name: "registrar_bem_estar",
    description: "Registra bem-estar diário",
    inputSchema: {
      type: "object",
      properties: {
        athlete_id: { type: "integer" },
        qualidade_sono: { type: "integer", minimum: 1, maximum: 10 },
        nivel_estresse: { type: "integer", minimum: 1, maximum: 10 },
        nivel_fadiga: { type: "integer", minimum: 1, maximum: 10 },
        dores_musculares: { type: "string", default: "Nenhuma" }
      },
      required: ["athlete_id", "qualidade_sono", "nivel_estresse", "nivel_fadiga"]
    },
    handler: (args) => callApi("POST", "/wellness/log", args)
  },
  {
    name: "gerar_mesociclo",
    description: "Gera mesociclo de treino",
    inputSchema: {
      type: "object",
      properties: {
        athlete_id: { type: "integer" },
        objective: { type: "string" },
        duration_weeks: { type: "integer", minimum: 1, maximum: 52 },
        sessions_per_week: { type: "integer", minimum: 1, maximum: 14 },
        progression_model: { type: "string" }
      },
      required: ["athlete_id", "objective", "duration_weeks", "sessions_per_week", "progression_model"]
    },
    handler: (args) => callApi("POST", "/planning/generate-mesocycle", args)
  },
  {
    name: "gerar_relatorio_atleta",
    description: "Relatório de atleta",
    inputSchema: {
      type: "object",
      properties: { athlete_id: { type: "integer" } },
      required: ["athlete_id"]
    },
    handler: ({ athlete_id }) => callApi("GET", `/reports/athlete-report/${athlete_id}`)
  },
  {
    name: "gerar_relatorio_equipe",
    description: "Relatório de equipe",
    inputSchema: { type: "object", properties: {} },
    handler: () => callApi("GET", "/reports/team-report")
  },
  {
    name: "gerar_grafico_performance",
    description: "Gera gráfico de performance",
    inputSchema: {
      type: "object",
      properties: {
        athlete_id: { type: "integer" },
        metric_name: { type: "string" }
      },
      required: ["athlete_id", "metric_name"]
    },
    handler: (args) => callApi("GET", "/charts/performance-chart", {}, args)
  }
];

// Cria MCP server
const mcp = createMcpServer({
  name: "vector-ai-sports",
  version: "1.0.0",
  tools
});

const app = express();

// Health check
app.get("/", (req, res) => {
  res.json({
    message: "Vector AI MCP Server (Node) está rodando",
    version: "1.0.0",
    mcp_endpoint: "/mcp (SSE)",
    tools_count: tools.length,
    vector_api_url: VECTOR_API_URL,
    status: "online"
  });
});

// Monta SSE direto em /mcp
app.use("/mcp", mcp);

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`🚀 Vector AI MCP rodando em http://0.0.0.0:${PORT}/mcp`);
});

