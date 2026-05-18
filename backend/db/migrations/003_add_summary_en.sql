-- Migration 003: 加 AI 英文解读字段 (summary_en + insights_en)
-- 在 Supabase Dashboard → SQL Editor 跑一次

ALTER TABLE papers
  ADD COLUMN IF NOT EXISTS summary_en text,
  ADD COLUMN IF NOT EXISTS insights_en text[] DEFAULT array[]::text[];

-- 验证：
--   SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'papers' AND column_name IN ('summary_en', 'insights_en');
