-- Paperscope Supabase Schema
-- 按文档 §5.2 设计，仅存论文索引，详情实时拉取

-- ========== 论文索引表 ==========
create table if not exists papers (
  id              text primary key,              -- 统一ID: arxiv:xxxx 或 s2:xxxx 或 doi:xxxx
  source          text not null,                  -- arxiv / s2 / pubmed
  source_id       text,                           -- 各平台原始ID
  title           text not null,
  authors         jsonb default '[]'::jsonb,      -- [{name, s2_id, affiliation}]
  venue           text,                           -- NeurIPS / Nature Medicine / arXiv
  venue_type      text,                           -- conference / journal / preprint
  venue_tier      text,                           -- CCF-A / T1 / Nature子刊 / ...
  year            int,
  published_at    date,
  citation_count  int default 0,
  reference_count int default 0,
  fields_of_study jsonb default '[]'::jsonb,     -- SS fieldsOfStudy
  domains         text[] default array[]::text[], -- world_model / physical_ai / medical_ai
  tasks           text[] default array[]::text[], -- 任务子标签
  paper_type      text,                           -- Method / Dataset / Survey
  open_access_pdf text,
  arxiv_url       text,
  doi             text,
  abstract_excerpt text,                          -- 摘要前200字，完整摘要实时拉
  code_links      jsonb default '[]'::jsonb,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

create index if not exists idx_papers_domains on papers using gin(domains);
create index if not exists idx_papers_tasks on papers using gin(tasks);
create index if not exists idx_papers_venue on papers(venue);
create index if not exists idx_papers_year on papers(year desc);
create index if not exists idx_papers_citations on papers(citation_count desc);
create index if not exists idx_papers_published on papers(published_at desc);

-- ========== 引用增长/热度快照（周更） ==========
create table if not exists paper_stats (
  paper_id        text references papers(id) on delete cascade,
  snapshot_date   date not null,
  citation_count  int default 0,
  view_count      int default 0,
  favorite_count  int default 0,
  primary key (paper_id, snapshot_date)
);

create index if not exists idx_stats_snapshot on paper_stats(snapshot_date desc);

-- ========== 用户扩展信息 ==========
create table if not exists user_profiles (
  user_id   uuid primary key references auth.users(id) on delete cascade,
  nickname  text,
  avatar_url text,
  created_at timestamptz default now()
);

-- ========== 收藏表 ==========
create table if not exists favorites (
  user_id    uuid references auth.users(id) on delete cascade,
  paper_id   text references papers(id) on delete cascade,
  created_at timestamptz default now(),
  primary key (user_id, paper_id)
);

-- ========== 笔记表 ==========
create table if not exists notes (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid references auth.users(id) on delete cascade,
  paper_id   text references papers(id) on delete cascade,
  content    text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_notes_user on notes(user_id);

-- ========== 阅读历史 ==========
create table if not exists read_history (
  user_id  uuid references auth.users(id) on delete cascade,
  paper_id text references papers(id) on delete cascade,
  read_at  timestamptz default now(),
  primary key (user_id, paper_id)
);

-- ========== 每周精选 ==========
create table if not exists weekly_picks (
  id           uuid primary key default gen_random_uuid(),
  week_start   date not null,
  domain       text not null,                    -- world_model / physical_ai / medical_ai
  paper_ids    text[] not null,
  summary_md   text,                              -- LLM 生成的每周摘要
  created_at   timestamptz default now(),
  unique (week_start, domain)
);

-- ========== Row Level Security ==========
alter table papers enable row level security;
alter table paper_stats enable row level security;
alter table user_profiles enable row level security;
alter table favorites enable row level security;
alter table notes enable row level security;
alter table read_history enable row level security;
alter table weekly_picks enable row level security;

-- 论文对所有人可读
create policy papers_public_read on papers for select using (true);
create policy stats_public_read on paper_stats for select using (true);
create policy weekly_public_read on weekly_picks for select using (true);

-- 用户数据仅本人可读写
create policy profiles_own on user_profiles for all using (auth.uid() = user_id);
create policy favorites_own on favorites for all using (auth.uid() = user_id);
create policy notes_own on notes for all using (auth.uid() = user_id);
create policy history_own on read_history for all using (auth.uid() = user_id);
