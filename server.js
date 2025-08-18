import express from "express";
import cors from "cors";
import axios from "axios";

const app = express();
app.use(cors());
app.use(express.json());

const VECTOR_API_URL = process.env.VECTOR_API_URL || "https://vectorapi.up.railway.app/v1";

// ----------------- Helper -----------------
async function callApi(method, endpoint, data = {}, params = {}) {
  console.log("📡 Enviando requisição para API:", {
    method,
    url: `${VECTOR_API_URL}${endpoint}`,
    data,
    params
  });

  try {
    const res = await axios({
      method,
      url: `${VECTOR_API_URL}${endpoint}`,
      data,
      params
    });

    console.log("✅ Resposta da API:", res.status, res.data);
    return res.data;
  } catch (err) {
    console.error("❌ Erro na API:", {
      status: err.response?.status,
      detalhe: err.response?.data || err.message
    });
    return {
      status: "erro",
      codigo: err.response?.status,
      detalhe: err.response?.data || err.message
    };
  }
}
// ----------------- Tools adaptadas para os Schemas -----------------
const tools = [
  // ----------------- Gestão de Atletas -----------------
  {
    name: "adicionar_atleta",
    description: "Cadastra um novo atleta",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string" },
        profile_data: { type: "object", default: {} }
      },
      required: ["name"]
    },
    handler: (args) =>
      callApi("POST", "/athletes/", {
        name: args.name,
        profile_data: args.profile_data || {}
      })
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
      properties: { athlete_name: { type: "string" } },
      required: ["athlete_name"]
    },
    handler: ({ athlete_name }) =>
      callApi("GET", `/athletes/${athlete_name}`)
  },
  {
    name: "deletar_atleta",
    description: "Remove atleta pelo nome",
    inputSchema: {
      type: "object",
      properties: { athlete_name: { type: "string" } },
      required: ["athlete_name"]
    },
    handler: async ({ athlete_name }) => {
      const atleta = await callApi("GET", `/athletes/${athlete_name}`);
      if (atleta?.id) return callApi("DELETE", `/athletes/${atleta.id}`);
      return { status: "erro", detalhe: "Atleta não encontrado" };
    }
  },

  // ----------------- Registro de Dados -----------------
  {
    name: "registrar_treino",
    description: "Registra treino para atleta",
    inputSchema: {
      type: "object",
      properties: {
        athlete_name: { type: "string" },
        workout_details: { type: "string" }
      },
      required: ["athlete_name", "workout_details"]
    },
    handler: (args) =>
      callApi("POST", "/workouts/", {
        athlete_name: args.athlete_name,
        workout_details: args.workout_details
      })
  },
  {
    name: "registrar_avaliacao",
    description: "Registra avaliação formal",
    inputSchema: {
      type: "object",
      properties: {
        athlete_name: { type: "string" },
        tipo_avaliacao: { type: "string" },
        resultados: { type: "object" }
      },
      required: ["athlete_name", "tipo_avaliacao", "resultados"]
    },
    handler: (args) =>
      callApi("POST", "/assessments/", {
        athlete_name: args.athlete_name,
        tipo_avaliacao: args.tipo_avaliacao,
        resultados: args.resultados
      })
  },
  {
    name: "registrar_bem_estar",
    description: "Registra bem-estar diário do atleta",
    inputSchema: {
      type: "object",
      properties: {
        athlete_name: { type: "string" },
        qualidade_sono: { type: "string" },
        nivel_estresse: { type: "string" },
        dores_musculares: { type: "string" },
        prontidao_cmj: { type: "string" }
      },
      required: ["athlete_name", "qualidade_sono", "nivel_estresse"]
    },
    handler: (args) =>
      callApi("POST", "/wellness/log", {
        athlete_name: args.athlete_name,
        qualidade_sono: args.qualidade_sono,
        nivel_estresse: args.nivel_estresse,
        dores_musculares: args.dores_musculares || "Nenhuma",
        prontidao_cmj: args.prontidao_cmj || null
      })
  },

  // ----------------- Planejamento -----------------
  {
    name: "gerar_mesociclo",
    description: "Gera mesociclo de treino",
    inputSchema: {
      type: "object",
      properties: {
        athlete_name: { type: "string" },
        meso_name: { type: "string" },
        start_date: { type: "string" },
        duracao_semanas: { type: "string" },
        progression_type: { type: "string" },
        progression_details: { type: "object" }
      },
      required: ["athlete_name", "meso_name", "duracao_semanas", "progression_type"]
    },
    handler: (args) =>
      callApi("POST", "/planning/generate-mesocycle", {
        athlete_name: args.athlete_name,
        meso_name: args.meso_name,
        start_date: args.start_date,
        duracao_semanas: args.duracao_semanas,
        progression_type: args.progression_type,
        progression_details: args.progression_details || {}
      })
  },

  // ----------------- Relatórios -----------------
  {
    name: "gerar_relatorio_atleta",
    description: "Gera relatório completo de atleta",
    inputSchema: {
      type: "object",
      properties: { athlete_name: { type: "string" } },
      required: ["athlete_name"]
    },
    handler: ({ athlete_name }) =>
      callApi("GET", `/reports/athlete-report/${athlete_name}`)
  },
  {
    name: "gerar_relatorio_equipe",
    description: "Gera relatório consolidado da equipe",
    inputSchema: { type: "object", properties: {} },
    handler: () => callApi("GET", "/reports/team-report")
  },

  // ----------------- Análises Gráficas -----------------
  {
    name: "gerar_grafico_performance",
    description: "Gera gráfico de performance de uma métrica",
    inputSchema: {
      type: "object",
      properties: {
        athlete_name: { type: "string" },
        metric_name: { type: "string" }
      },
      required: ["athlete_name", "metric_name"]
    },
    handler: (args) =>
      callApi("GET", "/charts/performance-chart", {}, {
        athlete_name: args.athlete_name,
        metric_name: args.metric_name
      })
  }
];


// ----------------- JSON-RPC Handler -----------------
app.post("/mcp", async (req, res) => {
  const { jsonrpc, id, method, params } = req.body;
  let result, error;

  if (method === "initialize") {
    result = {
      protocolVersion: "2024-11-05",
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: "vector-ai-sports", version: "1.0.0" }
    };
  } else if (method === "tools/list") {
    result = { tools };
  } else if (method === "tools/call") {
    const { name, arguments: args } = params;
    const tool = tools.find(t => t.name === name);
    if (!tool) {
      error = { code: -32601, message: "Tool não encontrada" };
    } else {
      result = await tool.handler(args || {});
    }
  } else {
    error = { code: -32601, message: `Method not found: ${method}` };
  }

  res.json({ jsonrpc: "2.0", id, result, error });
});

// ----------------- Health Check -----------------
app.get("/", (req, res) => {
  res.json({
    message: "Vector AI MCP Server está rodando",
    version: "1.0.0",
    mcp_endpoint: "/mcp (HTTP JSON-RPC)",
    tools_count: tools.length,
    vector_api_url: VECTOR_API_URL,
    status: "online"
  });
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`🚀 Vector AI MCP rodando em http://0.0.0.0:${PORT}/mcp`);
});
