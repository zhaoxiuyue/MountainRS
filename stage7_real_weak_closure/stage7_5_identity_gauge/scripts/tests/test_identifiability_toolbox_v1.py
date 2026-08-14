#!/usr/bin/env python3
"""Stage 7.5 工具箱固定 fixture。

每个 fixture 都是**已知答案**的合成案例：答案由解析推导给出，不由工具箱产生。
工具箱的职责是复现这些已知答案；复现不了就是工具箱错，不是 fixture 错。

覆盖六种情形，其中 F5、F6 是最容易被混淆的两对：
  F5  E 类条件量不进被估计侧 —— 参数多不等于自由度多
  F6  结构可分但数据不够   —— 实际不可辨识,与结构不可辨识处置完全不同
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from identifiability_toolbox_v1 import (  # noqa: E402
    ModelSpec, check_equivalence_and_dof, check_multistart, check_perturbation,
    check_numerical_rank, check_singular_spectrum, run_all,
)

RNG = np.random.default_rng(20260814)
X = np.linspace(0.15, 0.95, 60)          # 模拟 mu,取值域与真实 mu 一致
FLAT_X = np.full(60, 0.5) + 1e-9 * RNG.standard_normal(60)  # 几乎不变的因子


# ---------------------------------------------------------------- fixtures
def f1_single_param() -> ModelSpec:
    """y = a·x。当前项目的实际模型形状。已知：秩 1，可辨识。"""
    return ModelSpec(
        name="F1_single_param",
        params=["a"], conditions=["x"],
        jacobian=lambda th: X.reshape(-1, 1),
        predict=lambda th: th[0] * X,
    )


def f2_multiplicative_collinear() -> ModelSpec:
    """y = T·a·x。已知：列数 2、秩 1，零空间方向 (1,-1)/√2 的对数形式。"""
    return ModelSpec(
        name="F2_multiplicative_collinear",
        params=["T", "a"], conditions=["x"],
        jacobian=lambda th: np.column_stack([th[1] * X, th[0] * X]),
        predict=lambda th: th[0] * th[1] * X,
    )


def f3_additive_separable() -> ModelSpec:
    """y = a·x + b。已知：秩 2，可辨识（x 有变化）。"""
    return ModelSpec(
        name="F3_additive_separable",
        params=["a", "b"], conditions=["x"],
        jacobian=lambda th: np.column_stack([X, np.ones_like(X)]),
        predict=lambda th: th[0] * X + th[1],
    )


def f4_scaled_affine() -> ModelSpec:
    """y = T·(a·x + b)。已知：列数 3、秩 2，T 与 (a,b) 整体共线。"""
    def jac(th):
        T, a, b = th
        return np.column_stack([a * X + b, T * X, T * np.ones_like(X)])
    return ModelSpec(
        name="F4_scaled_affine",
        params=["T", "a", "b"], conditions=["x"],
        jacobian=jac,
        predict=lambda th: th[0] * (th[1] * X + th[2]),
    )


def f5_condition_quantity_excluded() -> ModelSpec:
    """y = a·x，x 是已知条件量（E 类）。已知：待估自由度 1，不是 2。"""
    return ModelSpec(
        name="F5_condition_quantity_excluded",
        params=["a"], conditions=["x", "sun_elevation", "cos_i"],
        jacobian=lambda th: X.reshape(-1, 1),
        predict=lambda th: th[0] * X,
    )


def f6_practically_unidentifiable() -> ModelSpec:
    """y = a·x + b，但 x 几乎是常数。已知：结构上秩 2，数值上条件数爆炸。"""
    return ModelSpec(
        name="F6_practically_unidentifiable",
        params=["a", "b"], conditions=["x"],
        jacobian=lambda th: np.column_stack([FLAT_X, np.ones_like(FLAT_X)]),
        predict=lambda th: th[0] * FLAT_X + th[1],
    )


# ------------------------------------------------------------------ 断言
def expect(label: str, got, want, results: list[tuple[str, bool, str]]) -> None:
    ok = got == want
    results.append((label, ok, f"期望 {want}，得到 {got}"))


def main() -> int:
    r: list[tuple[str, bool, str]] = []

    # F1 单参数：秩 1 可辨识；奇异值谱与等价替代两项应判 not_applicable
    m = f1_single_param()
    expect("F1 秩=1", check_numerical_rank(m, np.array([0.4])).values["rank"], 1, r)
    expect("F1 可辨识", check_numerical_rank(m, np.array([0.4])).values["identifiable_by_rank"], True, r)
    expect("F1 奇异值谱不适用", check_singular_spectrum(m, np.array([0.4])).status, "not_applicable", r)
    expect("F1 等价替代不适用", check_equivalence_and_dof(m, np.array([0.4])).status, "not_applicable", r)

    # F2 乘性共线：列 2 秩 1，零空间同时牵涉 T 与 a
    m = f2_multiplicative_collinear()
    rk = check_numerical_rank(m, np.array([0.8, 0.5]))
    expect("F2 秩=1", rk.values["rank"], 1, r)
    expect("F2 亏损=1", rk.values["deficiency"], 1, r)
    eq = check_equivalence_and_dof(m, np.array([0.8, 0.5]))
    expect("F2 不可辨识自由度=1", eq.values["unidentifiable_dof"], 1, r)
    expect("F2 等价组牵涉两个参数", set(eq.values["equivalence_groups"][0].keys()), {"T", "a"}, r)
    pert = check_perturbation(m, np.array([0.8, 0.5]))
    joint = pert.values["joint_null_direction"]
    single_max = max(pert.values["single_param_prediction_change"].values())
    # 沿零空间移动时一阶项抵消，只剩 O(eps^2)；判据用数量级之比，不用绝对阈值
    expect("F2 联合扰动比单参数扰动小 3 个数量级以上",
           bool(joint["prediction_change_norm"] < single_max * 1e-3), True, r)

    # F3 加性可分：秩 2
    m = f3_additive_separable()
    expect("F3 秩=2", check_numerical_rank(m, np.array([0.4, 0.05])).values["rank"], 2, r)
    expect("F3 无不可辨识自由度",
           check_equivalence_and_dof(m, np.array([0.4, 0.05])).values["unidentifiable_dof"], 0, r)

    # F4 缩放仿射：列 3 秩 2
    m = f4_scaled_affine()
    rk = check_numerical_rank(m, np.array([0.9, 0.4, 0.05]))
    expect("F4 秩=2", rk.values["rank"], 2, r)
    expect("F4 亏损=1", rk.values["deficiency"], 1, r)
    eq = check_equivalence_and_dof(m, np.array([0.9, 0.4, 0.05]))
    expect("F4 等价组含 T", "T" in eq.values["equivalence_groups"][0], True, r)

    # F5 条件量不占自由度：声明了 3 个 condition 但待估仍只有 1
    m = f5_condition_quantity_excluded()
    eq = check_equivalence_and_dof(m, np.array([0.4]))
    expect("F5 有效自由度=1", eq.values["effective_dof"], 1, r)
    expect("F5 条件量被排除在被估计侧", eq.values["condition_quantities_excluded"],
           ["x", "sun_elevation", "cos_i"], r)

    # F6 实际不可辨识：模型式子里 a 与 b 显然可分（一个乘 x、一个不乘），
    # 但 x 几乎是常数，数值上两列共线。工具箱只能看到后者。
    m = f6_practically_unidentifiable()
    rk = check_numerical_rank(m, np.array([0.4, 0.05]))
    expect("F6 数值秩降为 1（尽管符号上可分）", rk.values["rank"], 1, r)
    expect("F6 结果带有『非符号结构秩』的 caveat", "符号" in rk.values["caveat"], True, r)
    sp = check_singular_spectrum(m, np.array([0.4, 0.05]))
    expect("F6 条件数 > 1e6", bool(sp.values["condition_number"] > 1e6), True, r)

    # 关键局限：F2（真乘性共线）与 F6（数据变化不足）在数值上完全同形。
    # 二者的正确处置完全不同——前者必须改模型或固定 gauge，后者补数据即可——
    # 而工具箱给不出这个区分，必须由符号分析或解析证明补上。
    rk2 = check_numerical_rank(f2_multiplicative_collinear(), np.array([0.8, 0.5]))
    expect("F2 与 F6 的数值秩相同（工具箱无法区分二者）",
           rk.values["rank"] == rk2.values["rank"], True, r)
    expect("F2 与 F6 的秩亏也相同",
           rk.values["deficiency"] == rk2.values["deficiency"], True, r)

    # 多起点：F2 的秩与零空间方向在不同参数点上应保持一致
    m = f2_multiplicative_collinear()
    ms = check_multistart(m, [np.array([0.8, 0.5]), np.array([0.3, 1.2]), np.array([1.5, 0.2])])
    expect("多起点秩一致", ms.values["rank_consistent"], True, r)
    # 乘性共线的零空间方向 ∝ (T, -a)，随参数点变化——所以「方向稳定」不是判据。
    # 稳定的是秩，不是方向；把方向稳定当成不可辨识的证据会漏掉这一类。
    expect("多起点零空间方向随参数点变化（故不可作为判据）",
           ms.values["null_direction_stable"], False, r)
    expect("多起点 evidence_scope 上限为 profile", ms.evidence_scope, "profile", r)

    # 单起点时 multistart 必须判 not_applicable，而不是硬跑
    expect("单起点时多起点检查不适用",
           check_multistart(m, [np.array([0.8, 0.5])]).status, "not_applicable", r)

    # 观测数少于参数数时报 insufficient_data，不得归因为结构秩亏
    short = ModelSpec(name="short", params=["a", "b", "c"], conditions=[],
                      jacobian=lambda th: np.ones((2, 3)))
    expect("观测不足报 insufficient_data",
           check_numerical_rank(short, np.zeros(3)).status, "insufficient_data", r)

    # ------------------------------------------------------------ 输出
    passed = sum(1 for _, ok, _ in r if ok)
    for label, ok, detail in r:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  ({detail})"))
    print(f"\n{passed}/{len(r)} 通过")

    print("\n--- F1（当前项目实际模型形状）的完整检查清单 ---")
    for res in run_all(f1_single_param(), np.array([0.4])):
        print(f"  {res}")

    return 0 if passed == len(r) else 1


if __name__ == "__main__":
    sys.exit(main())
