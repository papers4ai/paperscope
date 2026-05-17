-- Migration 002: 加 AI 中文解读字段（summary_zh + insights）
-- 在 Supabase Dashboard → SQL Editor 跑一次

ALTER TABLE papers
  ADD COLUMN IF NOT EXISTS summary_zh text,
  ADD COLUMN IF NOT EXISTS insights text[] DEFAULT array[]::text[];

-- 全文索引可选（如果需要按 summary 内容搜索）
-- CREATE INDEX IF NOT EXISTS idx_papers_summary_zh ON papers USING gin(to_tsvector('simple', summary_zh));

-- 验证：
--   SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'papers' AND column_name IN ('summary_zh', 'insights');
