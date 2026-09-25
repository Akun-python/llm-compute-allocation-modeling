# -*- coding: utf-8 -*-
"""
统一绘图色系 (F题 华为杯 2026):
  水色 #88ada6 · 蔚蓝 #70f3ff · 蓝 #44cef6 · 碧蓝 #3eede7 · 石青 #1685a9 · 靛青 #177cb0
注册两个基于本色系的 matplotlib colormap:
  cyan_seq : 顺序 (浅→深), 用于连续数值
  cyan_div : 发散 (碧蓝→白→靛青), 用于正负值热图
"""
from matplotlib import colormaps
from matplotlib.colors import LinearSegmentedColormap

SEQUENTIAL = ["#70f3ff", "#44cef6", "#1685a9", "#177cb0"]
DIVERGENT = ["#3eede7", "#f4fcfd", "#177cb0"]

for _name, _colors in (
    ("cyan_seq", SEQUENTIAL),
    ("cyan_seq_r", SEQUENTIAL[::-1]),
    ("cyan_div", DIVERGENT),
    ("cyan_div_r", DIVERGENT[::-1]),
):
    colormaps.register(LinearSegmentedColormap.from_list(_name, _colors), name=_name)
