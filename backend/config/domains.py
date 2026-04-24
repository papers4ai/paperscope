"""三大研究领域定义。

领域关键词用于 arXiv/OpenAlex 查询 + 分类辅助。
子任务标签在 pipeline/classify.py 中使用。
"""

DOMAINS = {
    "world_model": {
        "label_zh": "World Model",
        "label_en": "World Model",
        "icon": "🌍",
        "description": "视频生成、场景重建、强化学习、Sim2Real 等构建智能体对世界建模的方法",
        "keywords": [
            "world model", "video generation", "video diffusion",
            "scene reconstruction", "neural radiance field", "NeRF",
            "model-based reinforcement learning", "sim-to-real",
            "foundation model", "action model", "predictive model",
        ],
    },
    "physical_ai": {
        "label_zh": "具身智能",
        "label_en": "Physical AI",
        "icon": "🤖",
        "description": "物理启发的神经网络、机器人学习、流体/气候模拟、3D重建",
        "keywords": [
            "physics-informed neural network", "PINN", "neural operator",
            "embodied AI", "robot learning", "robotic manipulation",
            "fluid simulation", "climate modeling", "3D reconstruction",
            "humanoid robot", "dexterous manipulation",
        ],
    },
    "medical_ai": {
        "label_zh": "医疗AI",
        "label_en": "Medical AI",
        "icon": "🏥",
        "description": "医学影像、癌症检测、药物发现、临床决策、手术导航",
        "keywords": [
            "medical imaging", "pathology", "cancer detection",
            "drug discovery", "molecular", "protein structure",
            "clinical decision support", "surgical navigation",
            "health monitoring", "medical vision-language model",
        ],
    },
}

DOMAIN_IDS = list(DOMAINS.keys())
