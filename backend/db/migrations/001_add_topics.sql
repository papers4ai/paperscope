-- Migration 001: 给 papers 表加 topics 列（LLM 生成的自由文本子主题）
-- 在 Supabase Dashboard → SQL Editor 跑一次

ALTER TABLE papers
  ADD COLUMN IF NOT EXISTS topics text[] DEFAULT array[]::text[];

CREATE INDEX IF NOT EXISTS idx_papers_topics ON papers USING gin(topics);

-- 验证：
--   SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'papers' AND column_name = 'topics';
