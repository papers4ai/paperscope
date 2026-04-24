// 前端运行时配置。部署时在 GitHub Pages 的 _config 或自定义构建步骤注入。
// 本地开发: 复制本文件到 config.local.js 并填入真实值。
export const SUPABASE_URL = window.__PAPERSCOPE_CONFIG__?.SUPABASE_URL || "";
export const SUPABASE_ANON_KEY = window.__PAPERSCOPE_CONFIG__?.SUPABASE_ANON_KEY || "";

// 供详情面板 fallback 使用（Supabase 没存完整摘要）
export const S2_PAPER_API = "https://api.semanticscholar.org/graph/v1/paper";

export const DOMAINS = {
  world_model: { label: "World Model", icon: "🌍" },
  physical_ai: { label: "Physical AI", icon: "🤖" },
  medical_ai:  { label: "Medical AI",  icon: "🏥" },
};
