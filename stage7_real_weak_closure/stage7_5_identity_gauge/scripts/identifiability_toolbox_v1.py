#!/usr/bin/env python3
"""Stage 7.5 可辨识性工具箱。

五组检查：数值秩/符号 gauge、Jacobian/奇异值/局部灵敏度、单项与联合扰动、
多起点或 profile、等价替代/重参数化/自由度占用审计。

**本工具箱的根本局限（必须随结论一起报告）：** 全部检查都是数值方法，而数值
方法分不清「结构不可辨识」与「数据变化不足」。F2（乘性共线）与 F6（结构可分
但因子几乎是常数）在奇异值谱上完全一样。要区分它们，只能回到模型式子做符号
分析或给出解析证明——那不在本工具箱的能力范围内。

两条贯穿全局的纪律：

1. **按数学适用性调用。** 对某对象不适用的检查返回 typed NOT_APPLICABLE 并附
   数学理由；不得为凑齐清单制造没有意义的测试。「实现麻烦」「数据不足」不是
   合法理由——前者不是数学判断，后者应报 INSUFFICIENT_DATA。

2. **局部结论不得升级为全局。** 本工具箱产出的一切数值结论（秩、奇异值、扰动、
   多起点一致性）在 evidence_scope 上最多是 local 或 profile。global 只能来自
   解析或结构证明，不由本工具箱签发。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

import numpy as np

Status = Literal["ok", "not_applicable", "insufficient_data"]


@dataclass
class CheckResult:
    check: str
    status: Status
    reason: str | None = None
    values: dict = field(default_factory=dict)
    evidence_scope: Literal["local", "profile", "none"] = "none"

    def __repr__(self) -> str:  # 便于 fixture 输出比对
        head = f"{self.check}: {self.status}"
        if self.status != "ok":
            return f"{head} — {self.reason}"
        return f"{head} {self.values}"


@dataclass
class ModelSpec:
    """一个可做可辨识性审计的模型。

    params      待估参数名，顺序即 Jacobian 的列序。
    conditions  已知条件量名（E 类）。它们不进入 Jacobian 的列，
                只作为构造 Jacobian 的输入。
    jacobian    theta -> (n_obs, n_params) 数组。
    """

    name: str
    params: list[str]
    conditions: list[str]
    jacobian: Callable[[np.ndarray], np.ndarray]
    predict: Callable[[np.ndarray], np.ndarray] | None = None

    @property
    def n_params(self) -> int:
        return len(self.params)


# -------------------------------------------------------------- 数值秩
def check_numerical_rank(model: ModelSpec, theta: np.ndarray,
                          rtol: float = 1e-10) -> CheckResult:
    """数值秩：在给定容差下，数据实际能看见几个参数方向。

    **这不是符号意义上的结构秩。** 数值 SVD 无法区分两种情形：
      (a) 参数在模型式子里只以固定组合出现——结构不可辨识，加数据无效；
      (b) 参数结构上可分，但当前数据在关键维度上变化太小——实际不可辨识，
          补充有新变化的数据即可解决。
    二者在奇异值谱上长得一模一样。要分辨只能回到模型式子做符号分析，
    或给出解析证明；本函数不承担该判断，也不得被当作该判断的替代。
    """
    J = np.asarray(model.jacobian(theta), dtype=float)
    if J.ndim != 2 or J.shape[1] != model.n_params:
        return CheckResult("numerical_rank", "not_applicable",
                           f"Jacobian 形状 {J.shape} 与参数个数 {model.n_params} 不匹配")
    if J.shape[0] < J.shape[1]:
        return CheckResult("numerical_rank", "insufficient_data",
                           f"观测数 {J.shape[0]} 少于参数数 {J.shape[1]}，秩必然亏损，"
                           f"此时秩亏不能归因于模型结构")
    s = np.linalg.svd(J, compute_uv=False)
    tol = max(J.shape) * s[0] * rtol if s[0] > 0 else 0.0
    rank = int((s > tol).sum())
    return CheckResult(
        "numerical_rank", "ok",
        values={"rank": rank, "n_params": model.n_params,
                "deficiency": model.n_params - rank,
                "identifiable_by_rank": rank == model.n_params,
                "tolerance": float(tol),
                "caveat": "数值秩,非符号结构秩;秩亏不能据此归因为结构不可辨识,"
                          "亦可能是数据在关键维度上变化不足"},
        evidence_scope="local",
    )


# -------------------------------------------------- 奇异值 / 条件数 / 零空间
def check_singular_spectrum(model: ModelSpec, theta: np.ndarray) -> CheckResult:
    J = np.asarray(model.jacobian(theta), dtype=float)
    if model.n_params == 1:
        s = np.linalg.svd(J, compute_uv=False)
        return CheckResult(
            "singular_spectrum", "not_applicable",
            reason="单参数模型的条件数恒为 1，奇异值谱不携带可辨识性信息；"
                   "该模型的可辨识性由 sigma>0 单条件决定，已由结构秩覆盖",
            values={"sigma": float(s[0]), "n_params": 1},
        )
    U, s, Vt = np.linalg.svd(J, full_matrices=False)
    cond = float(s[0] / s[-1]) if s[-1] > 0 else float("inf")
    null_dir = Vt[-1] if (s[-1] <= s[0] * 1e-10) else None
    values = {
        "singular_values": [float(x) for x in s],
        "condition_number": cond,
        "noise_amplification_factor": cond,
    }
    if null_dir is not None:
        values["null_space_direction"] = {
            p: round(float(v), 6) for p, v in zip(model.params, null_dir)
        }
    return CheckResult("singular_spectrum", "ok", values=values, evidence_scope="local")


# ------------------------------------------------------------ 局部灵敏度
def check_local_sensitivity(model: ModelSpec, theta: np.ndarray) -> CheckResult:
    J = np.asarray(model.jacobian(theta), dtype=float)
    norms = np.linalg.norm(J, axis=0)
    dead = [p for p, nrm in zip(model.params, norms) if nrm == 0.0]
    return CheckResult(
        "local_sensitivity", "ok",
        values={"column_norms": {p: float(n) for p, n in zip(model.params, norms)},
                "zero_influence_params": dead},
        evidence_scope="local",
    )


# -------------------------------------------------------- 单项 / 联合扰动
def check_perturbation(model: ModelSpec, theta: np.ndarray,
                       eps: float = 1e-4) -> CheckResult:
    """单项扰动看各参数的独立影响；联合扰动沿零空间方向走，看预测变不变。"""
    if model.predict is None:
        return CheckResult("perturbation", "not_applicable",
                           reason="该模型未提供 predict，无法比较扰动前后的预测")
    base = np.asarray(model.predict(theta), dtype=float)
    single = {}
    for i, p in enumerate(model.params):
        t = np.array(theta, dtype=float)
        t[i] += eps
        single[p] = float(np.linalg.norm(model.predict(t) - base))

    joint = None
    if model.n_params >= 2:
        J = np.asarray(model.jacobian(theta), dtype=float)
        _, s, Vt = np.linalg.svd(J, full_matrices=False)
        if s[-1] <= s[0] * 1e-10:
            d = Vt[-1]
            t = np.array(theta, dtype=float) + eps * d
            joint = {
                "direction": {p: round(float(v), 6) for p, v in zip(model.params, d)},
                "prediction_change_norm": float(np.linalg.norm(model.predict(t) - base)),
                "interpretation": "沿该方向移动而预测几乎不变，即为规范自由度方向",
            }
    return CheckResult(
        "perturbation", "ok",
        values={"single_param_prediction_change": single, "joint_null_direction": joint},
        evidence_scope="local",
    )


# ------------------------------------------------------------ 多起点 / profile
def check_multistart(model: ModelSpec, thetas: list[np.ndarray]) -> CheckResult:
    """多起点只回答『秩与零空间是否随参数点变化』，不签发全局结论。"""
    if len(thetas) < 2:
        return CheckResult("multistart", "not_applicable",
                           reason="少于两个起点，无法比较不同参数点的结构性质")
    ranks, dirs = [], []
    for t in thetas:
        r = check_numerical_rank(model, t)
        if r.status != "ok":
            return CheckResult("multistart", r.status, reason=r.reason)
        ranks.append(r.values["rank"])
        if model.n_params >= 2:
            J = np.asarray(model.jacobian(t), dtype=float)
            _, s, Vt = np.linalg.svd(J, full_matrices=False)
            if s[-1] <= s[0] * 1e-10:
                dirs.append(np.abs(Vt[-1]))
    consistent = len(set(ranks)) == 1
    dir_stable = None
    if len(dirs) >= 2:
        dir_stable = bool(np.allclose(dirs[0], dirs[-1], atol=1e-6))
    return CheckResult(
        "multistart", "ok",
        values={"ranks": ranks, "rank_consistent": consistent,
                "null_direction_stable": dir_stable,
                "scope_notice": "多起点一致不构成全局可辨识性证明，"
                                "无论重复多少次；本结果的 evidence_scope 上限为 profile"},
        evidence_scope="profile",
    )


# ------------------------------------------- 等价替代 / 自由度占用审计
def check_equivalence_and_dof(model: ModelSpec, theta: np.ndarray) -> CheckResult:
    """把秩亏方向翻译成『哪些参数被绑在一起』，并给出自由度账本。"""
    rank_r = check_numerical_rank(model, theta)
    if rank_r.status != "ok":
        return CheckResult("equivalence_and_dof", rank_r.status, reason=rank_r.reason)
    rank = rank_r.values["rank"]
    deficiency = model.n_params - rank

    if model.n_params == 1:
        # 即便本项检查不适用，「哪些量被排除在被估计侧」仍须报告：
        # 它是模型的固有属性，不随检查的适用性变化，且正是 E 类审计的核心事实。
        return CheckResult(
            "equivalence_and_dof", "not_applicable",
            reason="单参数模型不存在参数间的等价替代——等价替代至少需要两个参数",
            values={"effective_dof": rank, "declared_params": 1,
                    "condition_quantities_excluded": model.conditions},
        )

    groups = []
    if deficiency > 0:
        J = np.asarray(model.jacobian(theta), dtype=float)
        _, _, Vt = np.linalg.svd(J, full_matrices=False)
        for d in Vt[rank:]:
            involved = {p: round(float(v), 6)
                        for p, v in zip(model.params, d) if abs(v) > 1e-8}
            groups.append(involved)

    return CheckResult(
        "equivalence_and_dof", "ok",
        values={"declared_params": model.n_params,
                "effective_dof": rank,
                "unidentifiable_dof": deficiency,
                "equivalence_groups": groups,
                "condition_quantities_excluded": model.conditions},
        evidence_scope="local",
    )


ALL_CHECKS = [
    check_numerical_rank,
    check_singular_spectrum,
    check_local_sensitivity,
    check_perturbation,
    check_equivalence_and_dof,
]


def run_all(model: ModelSpec, theta: np.ndarray,
            multistart_thetas: list[np.ndarray] | None = None) -> list[CheckResult]:
    out = [fn(model, theta) for fn in ALL_CHECKS]
    if multistart_thetas:
        out.append(check_multistart(model, multistart_thetas))
    else:
        out.append(CheckResult("multistart", "not_applicable",
                               reason="未提供多起点，本次不做该项检查"))
    return out
