// Venue category translations
const venueCategories = {
  en: {
    "CCF-A 人工智能": "CCF-A AI",
    "CCF-A 计算机视觉": "CCF-A Computer Vision",
    "CCF-A 图形学/多媒体": "CCF-A Graphics/Multimedia",
    "CCF-A NLP": "CCF-A NLP",
    "统计 AI": "Statistical AI",
    "视觉 AI 顶刊": "Top Vision AI Journals",
    "机器学习期刊": "Machine Learning Journals",
    "图形学期刊": "Graphics Journals",
    "机器人顶会": "Top Robotics Conferences",
    "规划/多智能体": "Planning/Multi-Agent",
    "T1 机器人旗舰期刊": "T1 Flagship Robotics Journals",
    "T2 IEEE 期刊": "T2 IEEE Journals",
    "T3 专向期刊": "T3 Specialized Journals",
    "视觉 AI 共享期刊": "Shared Vision AI Journals",
    "医学专属顶会": "Top Medical Conferences",
    "医疗 ML 专属": "Medical ML Specialized",
    "HCI": "HCI",
    "T1 Nature/Science": "T1 Nature/Science",
    "T2 医学权威期刊": "T2 Top Medical Journals",
    "T3 医学影像专属": "T3 Medical Imaging",
    "T3 医学信息学": "T3 Medical Informatics",
    "T3 生物信息学": "T3 Bioinformatics",
    "T4 视觉 AI 通用": "T4 General Vision AI"
  },
  zh: {} // Chinese uses original category names
};

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
    filters: "Filters",
    hotResearchTopics: "Hot Research Topics",
    last6Months: "Last 6 months",
    researchRadar: "Research Direction Radar",
    radarDesc: "Performance of each field in different technical dimensions",
    deepAnalysis: "Hotspot Topic Deep Analysis",
    deepAnalysisDesc: "Analysis of core research directions in each field",
    coreHotspot: "Core Hotspot",
    emergingHotspot: "Emerging Hotspot",
    videoGenDesc: "Video generation technology has recently exploded, with continuous evolution of Diffusion model architectures, significantly improving text-to-video generation quality.",
    robotManipDesc: "Robot manipulation research focuses on dexterous operation and complex environment adaptation, combining large language models for more natural human-machine interaction.",
    drugDiscoveryDesc: "AI-assisted drug discovery has become a new growth point, combining molecular simulation and generative models to accelerate the drug development process.",
    heatIndex: "Heat Index",
    trend: "Trend",
    totalArXivPapers: "All arXiv Papers",
    subdirThisWeek: "Subcategories · New This Week",
    source: "Source",
    arxivPreprint: "arXiv Preprint",
    code: "Code",
    onlyWithCode: "Only show with open source code",
    year: "Year",
    all: "All",
    month: "Month",
    allMonths: "All months",
    jan: "Jan",
    feb: "Feb",
    mar: "Mar",
    apr: "Apr",
    may: "May",
    jun: "Jun",
    jul: "Jul",
    aug: "Aug",
    sep: "Sep",
    oct: "Oct",
    nov: "Nov",
    dec: "Dec",
    onlyFavorites: "Only show favorites",
    type: "Type",
    sort: "Sort",
    latestPublished: "Latest Published",
    mostCited: "Most Cited",
    allYears: "All Years",
    allMonths: "All Months",
    subdomainHint: "💡 Click on any domain tab above (🌍 World Model / 🤖 Physical AI / 🏥 Medical AI), or directly click the stats cards below to expand and view subcategories and new this week",
    subdomainSub: "Subcategories · {count} topics · Hover for details",
    showAll: "Show all {count} ↓",
    collapse: "Collapse ↑",
    articles: " articles",
    newThisWeek: ", {count} new this week",
    clearFilter: "Clear Filter ✕",
    noData: "No data",

    // Venue picker
    allDomains: "🔭 All Domains",
    selectDomainHint: "👆 Select a domain above to view top venues",
    allVenues: "All Venues",

    // Charts / Dashboard
    publishTrend: "Publication Trends",
    byYearDomain: "By Year × Domain",
    loading: "Loading...",
    noPapers: "No papers",
    loadingDetail: "Loading detail...",
    paperNotFound: "Paper not found",

    // Detail panel
    openPDF: "🔓 Open PDF",
    arxivSource: "arXiv Source",
    abstract: "Abstract",
    authors: "Authors",
    hotTopicHeat: "Hot Topic Heat",

    // Favorites & Tags
    allFavorites: "All Favorites",
    noFavorites: "No favorites yet. Click ☆ on any paper card to save it.",
    favNotLoaded: "Saved papers not yet loaded. Visit the Feed tab first.",
    tagNamePlaceholder: "Tag name",
    confirmTag: "✓ Create",
    cancelTag: "✕",
    addNewTag: "＋ New Tag",
    noTagsYet: "No tags yet",
    skipTag: "— Skip for now",
    deleteTagConfirm: "Delete tag \"{name}\"? Papers won't be deleted.",
    clearFavConfirm: "Clear all {n} favorites? (Tags will be kept)",
    noExportItems: "No favorites to export.",
    csvCols: "Title,Authors,Year,Venue,Tags,Citations,arXiv URL,PDF URL,Code URL",

    // Auth
    signIn: "Sign In",
    signUp: "Sign Up",
    email: "Email",
    password: "Password",
    forgotPassword: "Forgot Password?",
    signInWithGithub: "Sign in with GitHub",
    signOut: "Sign Out",

    // Detail panel
    back: "Back",

    // Radar chart labels
    radarGen: "Generation",
    radarPhysics: "Physics",
    radarControl: "Control",
    radarReasoning: "Reasoning",
    radarEfficiency: "Efficiency",
    radarGeneralization: "Generalization",

    // Topic tags
    tagTechBreakthrough: "Tech Breakthrough",
    tagFundamental: "Fundamental Research",
    tagMature: "Mature Application",

    // Gaussian Splatting topic card
    gaussianSplattingDesc: "3D reconstruction revolution: Gaussian Splatting enables real-time high-quality rendering, accelerating digital twin applications.",
    gaussianHeat: "Heat Index: 85/100",
    gaussianTrend: "Trend: +62%",

    // Fluid Dynamics topic card
    fluidDynamicsDesc: "Neural network-based fluid simulation advances with physics priors to improve accuracy and efficiency.",
    fluidHeat: "Heat Index: 78/100",
    fluidTrend: "Trend: +28%",

    // Medical Imaging topic card
    medicalImagingDesc: "Medical image analysis matures with multimodal fusion and self-supervised learning as new directions.",
    medicalHeat: "Heat Index: 88/100",
    medicalTrend: "Trend: +35%",

    // Trend predictions section
    trendPredictions: "Trend Predictions",
    trendPredictionsDesc: "Future research direction outlook based on data analysis",
    pred1Title: "Multimodal World Models",
    pred1Desc: "Unified world models integrating vision, language, and physics will become the research focus for more realistic virtual environment simulation.",
    pred1Tag: "2026-2027 Key Direction",
    pred2Title: "Real-time Physics Simulation",
    pred2Desc: "Neural network-based real-time physics simulation will be widely applied in robotics and gaming, breaking traditional numerical method limits.",
    pred2Tag: "2026-2027 Key Direction",
    pred3Title: "AI-assisted Precision Medicine",
    pred3Desc: "Combining large language models with medical data to achieve personalized treatment recommendations and disease risk prediction.",
    pred3Tag: "2026-2027 Key Direction",

    // Favorites modal
    myFavorites: "⭐ My Favorites",
    exportFav: "📥 Export ▾",
    exportTitle: "Export Favorites",
    clearFav: "🗑 Clear",
    jsonHint: "Dev / Backup",

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
    filters: "筛选器",
    hotResearchTopics: "热门研究方向",
    last6Months: "近 6 个月",
    researchRadar: "研究方向雷达图",
    radarDesc: "各领域在不同技术维度的表现",
    deepAnalysis: "热点主题深度分析",
    deepAnalysisDesc: "各领域核心研究方向解析",
    coreHotspot: "核心热点",
    emergingHotspot: "新兴热点",
    videoGenDesc: "视频生成技术近期爆发，Diffusion 模型架构持续演进，从文本到视频的生成质量大幅提升。",
    robotManipDesc: "机器人操控研究聚焦于灵巧操作和复杂环境适应，结合大语言模型实现更自然的人机交互。",
    drugDiscoveryDesc: "AI辅助药物发现成为新增长点，结合分子模拟和生成模型加速药物研发流程。",
    heatIndex: "热度指数",
    trend: "趋势",
    totalArXivPapers: "全部 arXiv 论文",
    subdirThisWeek: "细分方向 · 本周新增",
    source: "来源",
    arxivPreprint: "arXiv 预印本",
    code: "代码",
    onlyWithCode: "仅显示有开源代码",
    year: "年份",
    all: "全部",
    month: "月份",
    allMonths: "全部月份",
    jan: "1月",
    feb: "2月",
    mar: "3月",
    apr: "4月",
    may: "5月",
    jun: "6月",
    jul: "7月",
    aug: "8月",
    sep: "9月",
    oct: "10月",
    nov: "11月",
    dec: "12月",
    onlyFavorites: "仅显示收藏",
    type: "类型",
    sort: "排序",
    latestPublished: "最新发表",
    mostCited: "引用最多",
    subdomainHint: "💡 点击上方 <b>🌍 World Model</b> / <b>🤖 Physical AI</b> / <b>🏥 Medical AI</b> 任一领域 tab，<b>或直接点击下方统计卡片</b>，可展开查看该方向的细分主题与本周新增",
    subdomainSub: "细分方向 · 共 {count} 个主题 · 悬停查看说明",
    showAll: "查看全部 {count} ↓",
    collapse: "收起 ↑",
    articles: " 篇",
    newThisWeek: "，本周新增 {count}",
    clearFilter: "清除筛选 ✕",
    noData: "暂无数据",

    // Venue picker
    allDomains: "🔭 全部领域",
    selectDomainHint: "👆 请选择上方领域，查看对应的顶会/顶刊列表",
    allVenues: "全部期刊/会议",

    // Charts / Dashboard
    publishTrend: "发布趋势",
    byYearDomain: "按年份 × 领域",
    loading: "加载中...",
    noPapers: "暂无论文",
    loadingDetail: "加载详情...",
    paperNotFound: "论文不存在",

    // Detail panel
    openPDF: "🔓 打开 PDF",
    arxivSource: "arXiv 原文",
    abstract: "摘要",
    authors: "作者",
    hotTopicHeat: "热门主题热度",

    // Favorites & Tags
    allFavorites: "全部收藏",
    noFavorites: "还没有收藏的论文。点击论文卡片右上角的 ☆ 进行收藏。",
    favNotLoaded: "收藏的论文暂未加载，请先访问速览页面。",
    tagNamePlaceholder: "标签名称",
    confirmTag: "✓ 创建",
    cancelTag: "✕",
    addNewTag: "＋ 新建标签",
    noTagsYet: "暂无标签",
    skipTag: "— 暂不添加标签",
    deleteTagConfirm: "删除标签「{name}」？此操作不会删除论文。",
    clearFavConfirm: "确定清空全部 {n} 个收藏？（标签数据将保留）",
    noExportItems: "没有可导出的收藏论文。",
    csvCols: "标题,作者,年份,会议/期刊,标签,引用数,arXiv链接,PDF链接,代码链接",

    // Auth
    signIn: "登录",
    signUp: "注册",
    email: "邮箱",
    password: "密码",
    forgotPassword: "忘记密码？",
    signInWithGithub: "用 GitHub 登录",
    signOut: "退出登录",

    // Detail panel
    back: "返回",

    // Radar chart labels
    radarGen: "生成能力",
    radarPhysics: "物理建模",
    radarControl: "控制精度",
    radarReasoning: "推理深度",
    radarEfficiency: "数据效率",
    radarGeneralization: "泛化能力",

    // Topic tags
    tagTechBreakthrough: "技术突破",
    tagFundamental: "基础研究",
    tagMature: "成熟应用",

    // Gaussian Splatting topic card
    gaussianSplattingDesc: "3D重建技术革新，Gaussian Splatting实现实时高质量渲染，推动数字孪生应用落地。",
    gaussianHeat: "热度指数: 85/100",
    gaussianTrend: "趋势: +62%",

    // Fluid Dynamics topic card
    fluidDynamicsDesc: "基于神经网络的流体模拟取得进展，结合物理先验提升模拟精度和效率。",
    fluidHeat: "热度指数: 78/100",
    fluidTrend: "趋势: +28%",

    // Medical Imaging topic card
    medicalImagingDesc: "医学影像分析技术日趋成熟，多模态融合和自监督学习成为新方向。",
    medicalHeat: "热度指数: 88/100",
    medicalTrend: "趋势: +35%",

    // Trend predictions section
    trendPredictions: "趋势预测",
    trendPredictionsDesc: "基于数据分析的未来研究方向展望",
    pred1Title: "多模态世界模型",
    pred1Desc: "整合视觉、语言、物理的统一世界模型将成为研究焦点，实现更真实的虚拟环境模拟。",
    pred1Tag: "2026-2027 重点方向",
    pred2Title: "实时物理模拟",
    pred2Desc: "基于神经网络的实时物理模拟将在机器人和游戏领域广泛应用，突破传统数值方法限制。",
    pred2Tag: "2026-2027 重点方向",
    pred3Title: "AI辅助精准医疗",
    pred3Desc: "结合大语言模型和医学数据，实现个性化治疗方案推荐和疾病风险预测。",
    pred3Tag: "2026-2027 重点方向",

    // Favorites modal
    myFavorites: "⭐ 我的收藏",
    exportFav: "📥 导出 ▾",
    exportTitle: "导出收藏",
    clearFav: "🗑 清空",
    jsonHint: "开发者 / 备份",

    // Language
    language: "语言",
    english: "English",
    chinese: "中文",
    allYears: "全部年份",
    allMonths: "全部月份",
  }
};

let currentLang = localStorage.getItem('language') || 'en';

function t(key) {
  return i18n[currentLang][key] || key;
}

// Translate venue category names
function tVenueCategory(category) {
  return venueCategories[currentLang][category] || category;
}

function setLanguage(lang) {
  currentLang = lang;
  localStorage.setItem('language', lang);
  updateUI();
}

function updateUI() {
  // Update all data-i18n elements (including option elements)
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
