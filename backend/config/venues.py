"""顶会顶刊白名单 — 来自方案文档附录

每个 venue 有:
  - name: 官方名称 (用于 SS venue 查询)
  - aliases: 其他可能的名称变体
  - tier: 等级标签 (CCF-A / T1 / T2 / T3)
  - domains: 适用领域
"""

VENUES = {
    # ========== CCF-A 人工智能 (三领域通用) ==========
    "NeurIPS":     {"tier": "CCF-A", "type": "conference",
                    "aliases": ["NIPS", "Neural Information Processing Systems"],
                    "domains": ["world_model", "physical_ai", "medical_ai"]},
    "ICML":        {"tier": "CCF-A", "type": "conference",
                    "aliases": ["International Conference on Machine Learning"],
                    "domains": ["world_model", "physical_ai", "medical_ai"]},
    "ICLR":        {"tier": "CCF-A", "type": "conference",
                    "aliases": ["International Conference on Learning Representations"],
                    "domains": ["world_model", "physical_ai", "medical_ai"]},
    "AAAI":        {"tier": "CCF-A", "type": "conference", "aliases": [],
                    "domains": ["world_model", "physical_ai", "medical_ai"]},
    "IJCAI":       {"tier": "CCF-A", "type": "conference", "aliases": [],
                    "domains": ["world_model", "physical_ai"]},
    "COLT":        {"tier": "CCF-A", "type": "conference", "aliases": [],
                    "domains": ["world_model"]},

    # ========== CCF-A 计算机视觉 ==========
    "CVPR":        {"tier": "CCF-A", "type": "conference", "aliases": [],
                    "domains": ["world_model", "physical_ai", "medical_ai"]},
    "ICCV":        {"tier": "CCF-A", "type": "conference", "aliases": [],
                    "domains": ["world_model", "physical_ai", "medical_ai"]},
    "ECCV":        {"tier": "CCF-A", "type": "conference", "aliases": [],
                    "domains": ["world_model", "physical_ai", "medical_ai"]},

    # ========== CCF-A 图形学多媒体 ==========
    "SIGGRAPH":     {"tier": "CCF-A", "type": "conference", "aliases": [],
                     "domains": ["world_model", "physical_ai"]},
    "SIGGRAPH Asia":{"tier": "CCF-A", "type": "conference", "aliases": [],
                     "domains": ["world_model", "physical_ai"]},
    "ACM MM":       {"tier": "CCF-A", "type": "conference",
                     "aliases": ["ACM Multimedia"],
                     "domains": ["world_model", "physical_ai"]},
    "IEEE VIS":     {"tier": "CCF-A", "type": "conference", "aliases": [],
                     "domains": ["world_model"]},
    "IEEE VR":      {"tier": "CCF-A", "type": "conference", "aliases": [],
                     "domains": ["physical_ai"]},

    # ========== CCF-A NLP ==========
    "ACL":   {"tier": "CCF-A", "type": "conference", "aliases": [],
              "domains": ["world_model", "physical_ai", "medical_ai"]},
    "EMNLP": {"tier": "CCF-A", "type": "conference", "aliases": [],
              "domains": ["world_model", "physical_ai", "medical_ai"]},
    "NAACL": {"tier": "CCF-A", "type": "conference", "aliases": [],
              "domains": ["world_model", "physical_ai", "medical_ai"]},

    # ========== 统计 AI ==========
    "AISTATS": {"tier": "CCF-B", "type": "conference", "aliases": [],
                "domains": ["world_model"]},
    "UAI":     {"tier": "CCF-B", "type": "conference", "aliases": [],
                "domains": ["world_model"]},

    # ========== 机器人顶会 ==========
    "ICRA": {"tier": "机器人顶会", "type": "conference", "aliases": [],
             "domains": ["physical_ai"]},
    "IROS": {"tier": "机器人顶会", "type": "conference", "aliases": [],
             "domains": ["physical_ai"]},
    "CoRL": {"tier": "机器人顶会", "type": "conference",
             "aliases": ["Conference on Robot Learning"],
             "domains": ["physical_ai"]},
    "RSS":  {"tier": "机器人顶会", "type": "conference",
             "aliases": ["Robotics: Science and Systems"],
             "domains": ["physical_ai"]},

    # ========== 规划/多智能体 ==========
    "ICAPS": {"tier": "CCF-B", "type": "conference", "aliases": [],
              "domains": ["physical_ai"]},
    "AAMAS": {"tier": "CCF-B", "type": "conference", "aliases": [],
              "domains": ["physical_ai"]},
    "ISMAR": {"tier": "CCF-B", "type": "conference", "aliases": [],
              "domains": ["physical_ai"]},

    # ========== 医学专属顶会 ==========
    "MICCAI": {"tier": "医学顶会", "type": "conference", "aliases": [],
               "domains": ["medical_ai"]},
    "MIDL":   {"tier": "医学顶会", "type": "conference", "aliases": [],
               "domains": ["medical_ai"]},
    "CHIL":   {"tier": "医疗ML", "type": "conference", "aliases": [],
               "domains": ["medical_ai"]},
    "AMIA":   {"tier": "医疗ML", "type": "conference", "aliases": [],
               "domains": ["medical_ai"]},
    "CHI":    {"tier": "CCF-A", "type": "conference", "aliases": [],
               "domains": ["medical_ai"]},

    # ========== 视觉AI顶刊 (三领域通用) ==========
    "TPAMI": {"tier": "视觉顶刊", "type": "journal",
              "aliases": ["IEEE Transactions on Pattern Analysis and Machine Intelligence"],
              "domains": ["world_model", "physical_ai", "medical_ai"]},
    "IJCV":  {"tier": "视觉顶刊", "type": "journal",
              "aliases": ["International Journal of Computer Vision"],
              "domains": ["world_model", "physical_ai", "medical_ai"]},
    "TIP":   {"tier": "视觉顶刊", "type": "journal",
              "aliases": ["IEEE Transactions on Image Processing"],
              "domains": ["world_model", "physical_ai", "medical_ai"]},

    # ========== 机器学习期刊 ==========
    "JMLR":  {"tier": "ML顶刊", "type": "journal",
              "aliases": ["Journal of Machine Learning Research"],
              "domains": ["world_model", "physical_ai"]},
    "TMLR":  {"tier": "ML顶刊", "type": "journal",
              "aliases": ["Transactions on Machine Learning Research"],
              "domains": ["world_model", "physical_ai"]},
    "AIJ":   {"tier": "ML顶刊", "type": "journal",
              "aliases": ["Artificial Intelligence"], "domains": ["world_model"]},
    "TNNLS": {"tier": "ML顶刊", "type": "journal",
              "aliases": ["IEEE Transactions on Neural Networks and Learning Systems"],
              "domains": ["world_model"]},

    # ========== 图形学/多媒体期刊 ==========
    "ACM TOG":  {"tier": "图形学顶刊", "type": "journal",
                 "aliases": ["ACM Transactions on Graphics"],
                 "domains": ["world_model", "physical_ai"]},
    "IEEE TMM": {"tier": "多媒体顶刊", "type": "journal",
                 "aliases": ["IEEE Transactions on Multimedia"],
                 "domains": ["world_model"]},
    "TVCG":     {"tier": "图形学顶刊", "type": "journal",
                 "aliases": ["IEEE Transactions on Visualization and Computer Graphics"],
                 "domains": ["world_model", "physical_ai"]},
    "Pattern Recognition": {"tier": "CCF-B", "type": "journal", "aliases": [],
                            "domains": ["world_model"]},

    # ========== 机器人旗舰期刊 ==========
    "Science Robotics":             {"tier": "T1", "type": "journal", "aliases": [],
                                     "domains": ["physical_ai"]},
    "Nature Machine Intelligence":  {"tier": "T1", "type": "journal",
                                     "aliases": ["Nat Mach Intell"],
                                     "domains": ["world_model", "physical_ai", "medical_ai"]},
    "npj Robotics":                 {"tier": "T1", "type": "journal", "aliases": [],
                                     "domains": ["physical_ai"]},
    "IJRR": {"tier": "T1", "type": "journal",
             "aliases": ["International Journal of Robotics Research"],
             "domains": ["physical_ai"]},
    "TRO":  {"tier": "T1", "type": "journal",
             "aliases": ["IEEE Transactions on Robotics"],
             "domains": ["physical_ai"]},
    "RA-L": {"tier": "T2", "type": "journal",
             "aliases": ["IEEE Robotics and Automation Letters"],
             "domains": ["physical_ai"]},
    "T-ASE":{"tier": "T2", "type": "journal",
             "aliases": ["IEEE Transactions on Automation Science and Engineering"],
             "domains": ["physical_ai"]},
    "JFR":  {"tier": "T3", "type": "journal",
             "aliases": ["Journal of Field Robotics"],
             "domains": ["physical_ai"]},
    "Soft Robotics":      {"tier": "T3", "type": "journal", "aliases": [],
                           "domains": ["physical_ai"]},
    "Autonomous Robots":  {"tier": "T3", "type": "journal", "aliases": [],
                           "domains": ["physical_ai"]},
    "IJHR": {"tier": "T3", "type": "journal",
             "aliases": ["International Journal of Humanoid Robotics"],
             "domains": ["physical_ai"]},
    "Advanced Intelligent Systems": {"tier": "T3", "type": "journal", "aliases": [],
                                     "domains": ["physical_ai"]},

    # ========== Nature / Science 及子刊 (医学) ==========
    "Nature":   {"tier": "T1", "type": "journal", "aliases": [],
                 "domains": ["medical_ai"]},
    "Science":  {"tier": "T1", "type": "journal", "aliases": [],
                 "domains": ["medical_ai"]},
    "PNAS":     {"tier": "T1", "type": "journal",
                 "aliases": ["Proceedings of the National Academy of Sciences"],
                 "domains": ["medical_ai"]},
    "Nature Medicine":                  {"tier": "T1", "type": "journal",
                                         "aliases": ["Nat Med"], "domains": ["medical_ai"]},
    "Nature Methods":                   {"tier": "T1", "type": "journal",
                                         "aliases": ["Nat Methods"], "domains": ["medical_ai"]},
    "Nature Biomedical Engineering":    {"tier": "T1", "type": "journal",
                                         "aliases": ["Nat Biomed Eng"],
                                         "domains": ["medical_ai"]},
    "npj Digital Medicine":             {"tier": "T1", "type": "journal",
                                         "aliases": ["npj Digit Med"],
                                         "domains": ["medical_ai"]},
    "npj Precision Oncology":           {"tier": "T1", "type": "journal", "aliases": [],
                                         "domains": ["medical_ai"]},
    "Nature Communications":            {"tier": "T1", "type": "journal",
                                         "aliases": ["Nat Commun"],
                                         "domains": ["medical_ai"]},
    "Science Translational Medicine":   {"tier": "T1", "type": "journal",
                                         "aliases": ["Sci Transl Med"],
                                         "domains": ["medical_ai"]},

    # ========== 医学权威期刊 ==========
    "The Lancet":                {"tier": "T2", "type": "journal", "aliases": ["Lancet"],
                                  "domains": ["medical_ai"]},
    "The Lancet Digital Health": {"tier": "T2", "type": "journal",
                                  "aliases": ["Lancet Digit Health"],
                                  "domains": ["medical_ai"]},
    "NEJM AI": {"tier": "T2", "type": "journal", "aliases": [],
                "domains": ["medical_ai"]},
    "JAMA":    {"tier": "T2", "type": "journal", "aliases": [],
                "domains": ["medical_ai"]},
    "BMJ":     {"tier": "T2", "type": "journal", "aliases": [],
                "domains": ["medical_ai"]},
    "Cell":    {"tier": "T2", "type": "journal", "aliases": [],
                "domains": ["medical_ai"]},
    "Cell Systems": {"tier": "T2", "type": "journal", "aliases": [],
                     "domains": ["medical_ai"]},

    # ========== 医学影像专属期刊 ==========
    "TMI":           {"tier": "T3", "type": "journal",
                      "aliases": ["IEEE Transactions on Medical Imaging"],
                      "domains": ["medical_ai"]},
    "MIA":           {"tier": "T3", "type": "journal",
                      "aliases": ["Medical Image Analysis"], "domains": ["medical_ai"]},
    "Radiology":     {"tier": "T3", "type": "journal", "aliases": [],
                      "domains": ["medical_ai"]},
    "Radiology: AI": {"tier": "T3", "type": "journal",
                      "aliases": ["Radiology: Artificial Intelligence"],
                      "domains": ["medical_ai"]},

    # ========== 医学信息学期刊 ==========
    "JAMIA":     {"tier": "T3", "type": "journal",
                  "aliases": ["Journal of the American Medical Informatics Association"],
                  "domains": ["medical_ai"]},
    "IEEE JBHI": {"tier": "T3", "type": "journal",
                  "aliases": ["IEEE Journal of Biomedical and Health Informatics"],
                  "domains": ["medical_ai"]},
    "Artificial Intelligence in Medicine":  {"tier": "T3", "type": "journal",
                                             "aliases": ["Artif Intell Med"],
                                             "domains": ["medical_ai"]},
    "Journal of Biomedical Informatics":    {"tier": "T3", "type": "journal",
                                             "aliases": ["J Biomed Inform"],
                                             "domains": ["medical_ai"]},

    # ========== 生物信息学期刊 ==========
    "Bioinformatics":               {"tier": "T3", "type": "journal", "aliases": [],
                                     "domains": ["medical_ai"]},
    "Briefings in Bioinformatics":  {"tier": "T3", "type": "journal",
                                     "aliases": ["Brief Bioinform"],
                                     "domains": ["medical_ai"]},
    "IEEE TCBB": {"tier": "T3", "type": "journal",
                  "aliases": ["IEEE/ACM Transactions on Computational Biology and Bioinformatics"],
                  "domains": ["medical_ai"]},
    "BMC Bioinformatics": {"tier": "T3", "type": "journal", "aliases": [],
                           "domains": ["medical_ai"]},
}


def venues_for_domain(domain: str) -> list[str]:
    """返回某领域适用的所有 venue 名称。"""
    return [name for name, cfg in VENUES.items() if domain in cfg["domains"]]


def lookup_venue(name: str) -> dict | None:
    """按名称或别名查找 venue。"""
    name_lc = name.lower().strip()
    for official, cfg in VENUES.items():
        if official.lower() == name_lc:
            return {"name": official, **cfg}
        if any(a.lower() == name_lc for a in cfg.get("aliases", [])):
            return {"name": official, **cfg}
    return None
