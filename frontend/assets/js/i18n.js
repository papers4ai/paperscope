const i18n = {
  en: {
    // Navigation
    feed: "arXiv",
    curated: "Publications",
    trending: "Trending",
    favorites: "Favorites",
    login: "Login",

    // About Modal
    about: "About",
    aboutTitle: "About Paperscope",
    aboutDescription: "Your gateway to the latest AI research",
    features: "Features",
    feature1: "📡 Real-time arXiv paper tracking",
    feature2: "🏆 Publications from top conferences",
    feature3: "🔥 Trending research hotspots",
    feature4: "⭐ Favorites with tags and exports",
    contact: "Contact",
    email: "zhifengwang686@gmail.com",

    // Trending View
    worldModel: "World Model",
    worldModelDesc: "Virtual world construction and simulation",
    physicalAI: "Physical AI",
    physicalAIDesc: "Physical world perception and control",
    medicalAI: "Medical AI",
    medicalAIDesc: "Medical health intelligent applications",
    hotTopics: "Hot Topics",
    trendingComparison: "Trending Comparison",
    hotTopicsDesc: "Distribution of trending research topics in last 6 months",
    researchRadar: "Research Radar",
    researchRadarDesc: "Performance across different technical dimensions",
    hotTopicsDeep: "In-depth Hot Topic Analysis",
    videoGen: "Video Generation",
    gaussianSplatting: "Gaussian Splatting",
    roboticManipulation: "Robotic Manipulation",
    fluidDynamics: "Fluid Dynamics",
    drugDiscovery: "Drug Discovery",
    medicalImaging: "Medical Imaging",
    outlook: "Future Outlook",
    outlook1: "🚀 Multi-modal world models",
    outlook2: "⚡ Real-time physics simulation",
    outlook3: "💡 AI-assisted precision medicine",
    lastUpdated: "Last Updated",
    refresh: "Refresh",

    // Stats
    totalPapers: "Total Papers",
    thisWeek: "This Week",
    thisMonth: "This Month",
    hotTopicsCount: "Hot Topics",
    growthRate: "Growth Rate",

    // Filters
    filter: "Filter",
    domain: "Domain",
    source: "Source",
    year: "Year",
    paperType: "Paper Type",
    sortBy: "Sort By",
    venue: "Venue",
    tier: "Tier",
    hasCode: "Has Code",
    task: "Task",
    month: "Month",
    all: "All",
    arxiv: "arXiv",
    topConferences: "Top Conferences",
    journal: "Journal",
    lastUpdated: "Last Updated",
    relevance: "Relevance",
    citations: "Citations",

    // Dashboard
    dashboard: "Dashboard",
    search: "Search",
    stats: "Stats",
    statTrends: "Trends",
    statDistribution: "Distribution",

    // Auth
    signIn: "Sign In",
    signUp: "Sign Up",
    email: "Email",
    password: "Password",
    forgotPassword: "Forgot Password?",
    signInWithGithub: "Sign in with GitHub",
    signOut: "Sign Out",

    // Language
    language: "Language",
    english: "English",
    chinese: "中文",
  },
  zh: {
    // Navigation
    feed: "arXiv",
    curated: "出版物",
    trending: "热榜",
    favorites: "收藏",
    login: "登录",

    // About Modal
    about: "关于",
    aboutTitle: "关于 Paperscope",
    aboutDescription: "AI 研究前沿的入口",
    features: "功能介绍",
    feature1: "📡 实时追踪 arXiv 最新论文",
    feature2: "🏆 出版物顶会顶刊论文",
    feature3: "🔥 热门研究热点",
    feature4: "⭐ 收藏支持标签和导出",
    contact: "联系方式",
    email: "zhifengwang686@gmail.com",

    // Trending View
    worldModel: "World Model",
    worldModelDesc: "虚拟世界构建与模拟",
    physicalAI: "Physical AI",
    physicalAIDesc: "物理世界智能感知与控制",
    medicalAI: "Medical AI",
    medicalAIDesc: "医疗健康智能应用",
    hotTopics: "热门主题",
    trendingComparison: "领域热点对比",
    hotTopicsDesc: "近 6 个月各领域热门研究主题分布",
    researchRadar: "研究方向雷达图",
    researchRadarDesc: "各领域在不同技术维度的表现",
    hotTopicsDeep: "热点主题深度分析",
    videoGen: "视频生成",
    gaussianSplatting: "高斯溅射",
    roboticManipulation: "机器人操控",
    fluidDynamics: "流体动力学",
    drugDiscovery: "药物发现",
    medicalImaging: "医学影像",
    outlook: "未来展望",
    outlook1: "🚀 多模态世界模型",
    outlook2: "⚡ 实时物理模拟",
    outlook3: "💡 AI 辅助精准医疗",
    lastUpdated: "最后更新",
    refresh: "刷新",

    // Stats
    totalPapers: "论文总数",
    thisWeek: "本周",
    thisMonth: "本月",
    hotTopicsCount: "热门主题",
    growthRate: "增长率",

    // Filters
    filter: "筛选",
    domain: "领域",
    source: "来源",
    year: "年份",
    paperType: "论文类型",
    sortBy: "排序方式",
    venue: "期刊/会议",
    tier: "分类",
    hasCode: "有代码",
    task: "任务",
    month: "月份",
    all: "全部",
    arxiv: "arXiv",
    topConferences: "顶会",
    journal: "期刊",
    lastUpdated: "最新更新",
    relevance: "相关性",
    citations: "引用量",

    // Dashboard
    dashboard: "仪表盘",
    search: "搜索",
    stats: "统计",
    statTrends: "趋势",
    statDistribution: "分布",

    // Auth
    signIn: "登录",
    signUp: "注册",
    email: "邮箱",
    password: "密码",
    forgotPassword: "忘记密码？",
    signInWithGithub: "用 GitHub 登录",
    signOut: "退出登录",

    // Language
    language: "语言",
    english: "English",
    chinese: "中文",
  }
};

let currentLang = localStorage.getItem('language') || 'en';

function t(key) {
  return i18n[currentLang][key] || key;
}

function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('language', lang);
  updateUI();
}

function updateUI() {
  // Update all data-i18n elements
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  // Update all data-i18n-placeholder elements
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    el.placeholder = t(key);
  });
  // Update all data-i18n-title elements
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.getAttribute('data-i18n-title');
    el.title = t(key);
  });
}
