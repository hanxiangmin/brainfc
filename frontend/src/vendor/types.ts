export type Upload = {
  id: string;
  name: string;
  format?: string;
  variables: { name: string; shape: number[]; dtype?: string }[];
  suggested_kind?: string;
  suggested_variable?: string;
  suggested_matrix_kind?: string;
  warnings?: string[];
  error?: string;
};
export type Job = {
  id: string;
  status: string;
  progress: number;
  message: string;
  created_at: string;
  files: unknown[];
  results: { id: string; name: string }[];
  errors: { name: string; message: string }[];
};
export type Metrics = {
  global: Record<string, unknown>;
  nodes: Record<string, unknown>[];
  definitions?: Record<string, unknown>;
};
export type Result = {
  connectivity: number[][];
  roi_ids: string[];
  labels: string[];
  coordinates: number[][] | null;
  layouts?: {
    graph_2d?: {
      kind: "circular";
      coordinate_space: "display";
      units: "unitless";
      nodes: { id: string; x: number; y: number }[];
    };
  };
  graph: {
    edges: { id?: string; source: string; target: string; weight: number }[];
    metrics: Metrics;
  };
  hypergraph: {
    edges: { id: string | number; members: string[]; weight?: number }[];
    metrics: Metrics;
  };
  config: Record<string, unknown>;
  metadata: Record<string, unknown>;
  warnings: string[];
  version: string;
};
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api/v1" + path, init);
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail || body),
    );
  }
  return response.json();
}
export const post = (body?: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});
export function pretty(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number")
    return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(4);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
export const metricLabels: Record<string, string> = {
  weighted_hyperdegree: "加权超度",
  participation_fraction: "超边参与比例",
  mean_incident_edge_size: "参与超边平均大小",
  incident_edge_ids: "参与的超边 ID",
  n_positive_components: "正连接分量",
  n_memberships: "成员关系数量",
  mean_hyperdegree: "平均超度",
  max_edge_size: "最大超边大小",
  global_efficiency_positive: "正连接全局效率",
  mean_clustering_positive: "正连接平均聚类",
  degree_centrality: "度中心性",
  strength: "连接强度",
  clustering_positive: "正连接聚类",
  harmonic_centrality_positive: "正连接调和中心性",
  closeness_positive: "正连接接近中心性",
  betweenness_positive: "正连接介数中心性",
  community_positive: "正连接社区",
  n_nodes: "脑区数量",
  n_edges: "连接数量",
  density: "连接密度",
  n_components: "连通分量",
  components: "连通分量",
  global_efficiency: "全局效率",
  positive_global_efficiency: "正连接全局效率",
  average_clustering: "平均聚类",
  mean_clustering: "平均聚类",
  modularity: "模块度",
  n_hyperedges: "超边数量",
  mean_edge_size: "平均超边大小",
  average_edge_size: "平均超边大小",
  degree: "度",
  strength_positive: "正连接强度",
  strength_negative: "负连接强度",
  positive_strength: "正连接强度",
  negative_strength: "负连接强度",
  hyperdegree: "超度",
  clustering: "聚类系数",
  betweenness: "介数中心性",
  id: "脑区 ID",
};
