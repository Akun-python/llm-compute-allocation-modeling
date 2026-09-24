# -*- coding: utf-8 -*-
"""共享路径与常量：F题 华为杯 2026 求解工程"""
import os

BASE = r"C:\Users\24260\Desktop\研究生生涯\简历\数学建模国赛优秀论文\华为杯latex模板\第二十三届中国研究生数学建模竞赛 - 中文题目\中文题目\F题"
ATT = os.path.join(BASE, "real_attachments")
SOLVE = os.path.join(BASE, "solve")
CODE = os.path.join(SOLVE, "code")
RES = os.path.join(SOLVE, "results")
FIG = os.path.join(SOLVE, "figures")

for _d in (RES, FIG):
    os.makedirs(_d, exist_ok=True)

A = os.path.join(ATT, "A_data_value")
B = os.path.join(ATT, "B_scaling_laws")
C = os.path.join(ATT, "C_efficiency_evolution")

# ---- 17 个配方域与 13 个损失域 ----
MIX_DOMAINS = ["arxiv", "freelaw", "nih_exporter", "pubmed_central", "wikipedia_en",
               "dm_mathematics", "github", "philpapers", "stackexchange", "enron_emails",
               "gutenberg_pg_19", "pile_cc", "ubuntu_irc", "europarl", "hackernews",
               "pubmed_abstracts", "uspto_backgrounds"]
LOSS_DOMAINS = ["arxiv", "freelaw", "pubmed_central", "wikipedia_en", "dm_mathematics",
                "github", "stackexchange", "gutenberg_pg_19", "pile_cc", "ubuntu_irc",
                "hackernews", "pubmed_abstracts", "uspto_backgrounds"]

def mixture_cols(prefix="train_the_pile"):
    return [f"{prefix}_{d}" for d in MIX_DOMAINS]

def loss_cols():
    return [f"metric/the_pile_{d}_val_loss" for d in LOSS_DOMAINS]
