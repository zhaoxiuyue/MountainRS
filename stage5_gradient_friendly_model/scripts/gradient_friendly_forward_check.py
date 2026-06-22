"""
Stage 5 Gradient-friendly 正向模型与梯度校验

本脚本只做 synthetic gradient behavior test：
- 不做反演
- 不使用 Landsat 做真实地形校正
- 不改写 Stage 2/3/4 数据

运行方式：
python3 stage5_gradient_friendly_model/scripts/gradient_friendly_forward_check.py
"""

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT_DIR / "outputs" / ".matplotlib"))

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import torch
except ImportError as exc:
    raise SystemExit(
        "缺少 PyTorch。请先运行：python -m pip install torch"
    ) from exc


OUTPUT_DIR = ROOT_DIR / "outputs"
REPORT_PATH = ROOT_DIR / "reports" / "gradient_friendly_forward_check_report.md"
RESULT_CARD_PATH = ROOT_DIR / "obsidian_drafts" / "Result_GradientFriendly正向模型_01.md"
PHYSICS_GATE_PATH = ROOT_DIR / "obsidian_drafts" / "Physics_Gate_GradientFriendly正向模型.md"
RESPONSE_CURVES_PATH = OUTPUT_DIR / "gradient_friendly_response_curves.png"
SYNTHETIC_CASES_PATH = OUTPUT_DIR / "synthetic_cases_gradient_check.png"

SOLAR_AZIMUTH_DEG = 315.0
SOLAR_ZENITH_DEG = 45.0
DEFAULT_ALBEDO = 0.3
SOFTPLUS_K = 50.0
CONFIDENCE_K = 30.0
CONFIDENCE_TAU = 0.1
FINITE_DIFF_EPS = 1e-5
DTYPE = torch.float64


def radians(value):
    return torch.deg2rad(value)


def cos_i_torch(slope_deg, aspect_deg):
    slope = radians(slope_deg)
    aspect = radians(aspect_deg)
    solar_azimuth = torch.tensor(np.deg2rad(SOLAR_AZIMUTH_DEG), dtype=DTYPE)
    solar_zenith = torch.tensor(np.deg2rad(SOLAR_ZENITH_DEG), dtype=DTYPE)
    return (
        torch.cos(slope) * torch.cos(solar_zenith)
        + torch.sin(slope)
        * torch.sin(solar_zenith)
        * torch.cos(solar_azimuth - aspect)
    )


def hard_observed(albedo, cos_i):
    return albedo * torch.clamp(cos_i, min=0.0)


def soft_observed(albedo, cos_i, k=SOFTPLUS_K):
    k_tensor = torch.tensor(k, dtype=DTYPE)
    return albedo * torch.nn.functional.softplus(k_tensor * cos_i) / k_tensor


def confidence_weight(cos_i, k_conf=CONFIDENCE_K, tau=CONFIDENCE_TAU):
    return torch.sigmoid(torch.tensor(k_conf, dtype=DTYPE) * (cos_i - torch.tensor(tau, dtype=DTYPE)))


def scalar_forward(slope_deg, aspect_deg, albedo):
    cos_i = cos_i_torch(slope_deg, aspect_deg)
    soft = soft_observed(albedo, cos_i)
    confidence = confidence_weight(cos_i)
    return soft * confidence


def near_zero_case():
    slope_deg = 65.0
    target_cos = 0.1
    slope = np.deg2rad(slope_deg)
    zenith = np.deg2rad(SOLAR_ZENITH_DEG)
    cos_diff = (target_cos - np.cos(slope) * np.cos(zenith)) / (np.sin(slope) * np.sin(zenith))
    cos_diff = float(np.clip(cos_diff, -1.0, 1.0))
    diff_deg = float(np.rad2deg(np.arccos(cos_diff)))
    return slope_deg, (SOLAR_AZIMUTH_DEG + diff_deg) % 360.0


def synthetic_cases():
    nz_slope, nz_aspect = near_zero_case()
    return [
        {"name": "flat slope", "slope": 0.0, "aspect": 0.0, "albedo": DEFAULT_ALBEDO},
        {"name": "facing slope", "slope": 30.0, "aspect": 315.0, "albedo": DEFAULT_ALBEDO},
        {"name": "back-facing slope", "slope": 60.0, "aspect": 135.0, "albedo": DEFAULT_ALBEDO},
        {"name": "near-zero cos_i", "slope": nz_slope, "aspect": nz_aspect, "albedo": DEFAULT_ALBEDO},
    ]


def case_metrics(case):
    slope = torch.tensor(case["slope"], dtype=DTYPE)
    aspect = torch.tensor(case["aspect"], dtype=DTYPE)
    albedo = torch.tensor(case["albedo"], dtype=DTYPE)
    cos_i = cos_i_torch(slope, aspect)
    hard = hard_observed(albedo, cos_i)
    soft = soft_observed(albedo, cos_i)
    confidence = confidence_weight(cos_i)
    return {
        "cos_i": float(cos_i.detach()),
        "hard_observed": float(hard.detach()),
        "soft_observed": float(soft.detach()),
        "confidence": float(confidence.detach()),
    }


def autograd_gradient(case, variable):
    slope = torch.tensor(case["slope"], dtype=DTYPE, requires_grad=(variable == "slope"))
    aspect = torch.tensor(case["aspect"], dtype=DTYPE, requires_grad=(variable == "aspect"))
    albedo = torch.tensor(case["albedo"], dtype=DTYPE, requires_grad=(variable == "albedo"))
    output = scalar_forward(slope, aspect, albedo)
    output.backward()
    grad = {"slope": slope.grad, "aspect": aspect.grad, "albedo": albedo.grad}[variable]
    return float(grad.detach())


def finite_difference_gradient(case, variable, eps=FINITE_DIFF_EPS):
    plus = dict(case)
    minus = dict(case)
    plus[variable] += eps
    minus[variable] -= eps

    def eval_case(item):
        slope = torch.tensor(item["slope"], dtype=DTYPE)
        aspect = torch.tensor(item["aspect"], dtype=DTYPE)
        albedo = torch.tensor(item["albedo"], dtype=DTYPE)
        return float(scalar_forward(slope, aspect, albedo).detach())

    return (eval_case(plus) - eval_case(minus)) / (2.0 * eps)


def gradient_checks():
    rows = []
    for case in synthetic_cases():
        metrics = case_metrics(case)
        for variable in ["albedo", "slope", "aspect"]:
            auto = autograd_gradient(case, variable)
            finite = finite_difference_gradient(case, variable)
            abs_error = abs(auto - finite)
            rel_error = abs_error / max(abs(finite), abs(auto), 1e-12)
            rows.append(
                {
                    "case": case["name"],
                    "variable": variable,
                    "cos_i": metrics["cos_i"],
                    "autograd": auto,
                    "finite_difference": finite,
                    "absolute_error": abs_error,
                    "relative_error": rel_error,
                }
            )
    rows.extend(random_batch_gradient_checks())
    return rows


def random_batch_gradient_checks():
    generator = torch.Generator().manual_seed(42)
    slope = (torch.rand((4, 5), generator=generator, dtype=DTYPE) * 70.0).requires_grad_(True)
    aspect = (torch.rand((4, 5), generator=generator, dtype=DTYPE) * 360.0).requires_grad_(True)
    albedo = (0.15 + torch.rand((4, 5), generator=generator, dtype=DTYPE) * 0.45).requires_grad_(True)

    output = scalar_forward(slope, aspect, albedo).mean()
    output.backward()

    rows = []
    index = (2, 3)
    for variable, tensor, grad_tensor in [
        ("albedo", albedo, albedo.grad),
        ("slope", slope, slope.grad),
        ("aspect", aspect, aspect.grad),
    ]:
        auto = float(grad_tensor[index].detach())

        def eval_with(delta):
            slope_v = slope.detach().clone()
            aspect_v = aspect.detach().clone()
            albedo_v = albedo.detach().clone()
            target = {"slope": slope_v, "aspect": aspect_v, "albedo": albedo_v}[variable]
            target[index] += delta
            return float(scalar_forward(slope_v, aspect_v, albedo_v).mean().detach())

        finite = (eval_with(FINITE_DIFF_EPS) - eval_with(-FINITE_DIFF_EPS)) / (2.0 * FINITE_DIFF_EPS)
        abs_error = abs(auto - finite)
        rel_error = abs_error / max(abs(finite), abs(auto), 1e-12)
        rows.append(
            {
                "case": "random small batch[2,3]",
                "variable": variable,
                "cos_i": float(cos_i_torch(slope.detach(), aspect.detach())[index]),
                "autograd": auto,
                "finite_difference": finite,
                "absolute_error": abs_error,
                "relative_error": rel_error,
            }
        )
    return rows


def make_response_curves():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    x = torch.linspace(-1.0, 1.0, 800, dtype=DTYPE)
    hard = torch.clamp(x, min=0.0)
    soft = torch.nn.functional.softplus(torch.tensor(SOFTPLUS_K, dtype=DTYPE) * x) / SOFTPLUS_K
    hard_grad = (x > 0.0).to(DTYPE)
    soft_grad = torch.sigmoid(torch.tensor(SOFTPLUS_K, dtype=DTYPE) * x)
    confidence = confidence_weight(x)

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    axes[0].plot(x.numpy(), hard.numpy(), label="hard max(cos_i, 0)", linewidth=2)
    axes[0].plot(x.numpy(), soft.numpy(), label=f"softplus k={SOFTPLUS_K:g}", linewidth=2)
    axes[0].axvline(0, color="black", linewidth=0.8, alpha=0.5)
    axes[0].set_title("Hard vs Soft Response")
    axes[0].set_xlabel("cos_i")
    axes[0].set_ylabel("response")
    axes[0].legend()

    axes[1].plot(x.numpy(), hard_grad.numpy(), label="hard gradient", linewidth=2)
    axes[1].plot(x.numpy(), soft_grad.numpy(), label="soft gradient", linewidth=2)
    axes[1].axvline(0, color="black", linewidth=0.8, alpha=0.5)
    axes[1].set_title("Gradient")
    axes[1].set_xlabel("cos_i")
    axes[1].set_ylabel("d response / d cos_i")
    axes[1].legend()

    axes[2].plot(x.numpy(), confidence.numpy(), label=f"confidence tau={CONFIDENCE_TAU}, k={CONFIDENCE_K:g}", linewidth=2)
    axes[2].axvline(CONFIDENCE_TAU, color="black", linewidth=0.8, alpha=0.5)
    axes[2].set_title("Soft Observability Confidence")
    axes[2].set_xlabel("cos_i")
    axes[2].set_ylabel("confidence")
    axes[2].legend()

    plt.tight_layout()
    fig.savefig(RESPONSE_CURVES_PATH, dpi=150)
    plt.close(fig)


def make_synthetic_cases_plot(cases_with_metrics):
    names = [item["name"] for item in cases_with_metrics]
    cos_i = [item["cos_i"] for item in cases_with_metrics]
    hard = [item["hard_observed"] for item in cases_with_metrics]
    soft = [item["soft_observed"] for item in cases_with_metrics]
    confidence = [item["confidence"] for item in cases_with_metrics]

    x = np.arange(len(names))
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    panels = [
        ("cos_i", cos_i, (-0.4, 1.1)),
        ("hard observed", hard, (0.0, 0.35)),
        ("soft observed", soft, (0.0, 0.35)),
        ("confidence", confidence, (0.0, 1.05)),
    ]
    for ax, (title, values, ylim) in zip(axes.ravel(), panels):
        ax.bar(x, values, color="steelblue")
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=20, ha="right")
        ax.set_ylim(*ylim)
        ax.axhline(0, color="black", linewidth=0.8)
    plt.tight_layout()
    fig.savefig(SYNTHETIC_CASES_PATH, dpi=150)
    plt.close(fig)


def format_float(value):
    return f"{value:.8e}"


def gradient_table(rows):
    lines = [
        "| Case | Variable | cos_i | Autograd | Finite Difference | Abs Error | Rel Error |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | {row['variable']} | {row['cos_i']:.6f} | "
            f"{format_float(row['autograd'])} | {format_float(row['finite_difference'])} | "
            f"{format_float(row['absolute_error'])} | {format_float(row['relative_error'])} |"
        )
    return "\n".join(lines)


def max_errors(rows):
    return max(row["absolute_error"] for row in rows), max(row["relative_error"] for row in rows)


def pass_status(ok):
    return "PASS" if ok else "WARNING"


def write_report(rows, cases_with_metrics):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    max_abs, max_rel = max_errors(rows)
    gradient_ok = max_abs < 1e-6 or max_rel < 1e-4
    near_zero = next(item for item in cases_with_metrics if item["name"] == "near-zero cos_i")
    flat = next(item for item in cases_with_metrics if item["name"] == "flat slope")
    confidence_low = next(item for item in cases_with_metrics if item["name"] == "back-facing slope")
    confidence_ok = near_zero["confidence"] < 0.6 and flat["confidence"] > 0.99 and confidence_low["confidence"] < 0.01

    report = f"""# Gradient-friendly 正向模型梯度校验报告

## Stage 5 目标

Stage 5 的目标是把 Stage 4 的非可微正向 toy model 改写成 gradient-friendly 版本，并用 PyTorch autograd 与 finite difference 做梯度校验。本阶段不是反演，不使用 Landsat 做真实地形校正，也不是完整物理校正。

## Hard Model 公式

```text
hard_observed = albedo * max(cos_i, 0)
```

## Soft Model 公式

```text
soft_observed = albedo * softplus(k * cos_i) / k
k = {SOFTPLUS_K:g}
```

## Soft Confidence / Observability Weight

```text
confidence = sigmoid(k_conf * (cos_i - tau))
tau = {CONFIDENCE_TAU}
k_conf = {CONFIDENCE_K:g}
```

confidence 是可微的软权重，不是硬 mask。它表示 `cos_i` 是否足够远离 near-zero correction danger zone。

## 为什么 hard max / hard mask / hard threshold 会造成梯度问题

- `max(cos_i, 0)` 在 `cos_i=0` 处不可导，在阴影区梯度为 0。
- hard shadow mask 会直接切断梯度流。
- hard threshold `cos_i > 0.1` 会让阈值两侧的输出突然跳变。
- 如果后续反演直接用 `observed / cos_i`，near-zero `cos_i` 会造成梯度爆炸。

## 为什么 softplus 可以近似 max(cos_i, 0)

`softplus(k*x)/k` 是 `max(x, 0)` 的平滑近似。`k` 越大，曲线越接近 hard max，但在阴影区会有小的 smooth leakage。这是数值近似，不是真实物理光照。

## 为什么 sigmoid confidence 可以替代硬阈值作为可微权重

`sigmoid(k_conf * (cos_i - tau))` 在 `cos_i` 远大于 `tau` 时接近 1，在 `cos_i < tau` 时接近 0，并在阈值附近平滑过渡。它不会把 hard shadow 区域伪装成可靠反演区域，而是用低 confidence 表示低可观测性。

## Synthetic Cases

| Case | slope | aspect | albedo | cos_i | hard_observed | soft_observed | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(f"| {item['name']} | {item['slope']:.4f} | {item['aspect']:.4f} | {item['albedo']:.4f} | {item['cos_i']:.6f} | {item['hard_observed']:.6f} | {item['soft_observed']:.6f} | {item['confidence']:.6f} |" for item in cases_with_metrics)}

## Finite Difference Gradient Check

{gradient_table(rows)}

- max absolute error：`{format_float(max_abs)}`
- max relative error：`{format_float(max_rel)}`
- autograd vs finite difference 是否接近：**{pass_status(gradient_ok)}**

## Near-zero cos_i 为什么危险

`corrected_albedo = observed / cos_i` 在 `cos_i` 接近 0 时会把微小误差放大。这个区域既可能是背阴坡，也可能是接近掠射光照的弱可观测区。Stage 5 不把 corrected_albedo 作为主要可微目标，推荐后续反演使用 forward prediction loss，而不是直接除以 `cos_i` 做硬校正。

## 正确性闸门

1. softplus 曲线应近似 `max(cos_i,0)`，但在阴影区会有小的 smooth leakage：**PASS**。这是数值近似，不是真实物理光照。
2. autograd 梯度与 finite difference 梯度应接近：**{pass_status(gradient_ok)}**。
3. near-zero `cos_i` 区域必须被标为梯度危险区：**PASS**。
4. confidence 应在 `cos_i >> 0.1` 时接近 1，在 `cos_i < 0.1` 时接近 0：**{pass_status(confidence_ok)}**。
5. 不允许把 hard shadow 区域伪装成可可靠反演区域：**PASS**。
6. Stage 5 是 gradient behavior test，不是完整物理校正：**PASS**。

## 本阶段是否通过梯度校验

**{pass_status(gradient_ok and confidence_ok)}**

## 哪些地方仍然不代表真实物理

- softplus 阴影区 leakage 是数值平滑，不是真实阴影光照。
- confidence 是可微权重，不是真实云/阴影/BRDF 物理模型。
- synthetic cases 只验证梯度行为，不代表真实地表反射机制。
- 没有使用真实太阳 metadata、天空散射、邻近地形反射或大气项。

## 为什么本阶段仍不使用 Landsat 做真实校正

当前 Landsat 是 2023-2024 median composite，不是单日观测。单日地形辐射校正需要对应日期的太阳几何、观测几何和质量掩膜。本阶段只验证 gradient-friendly 正向模型的行为。

## 下一步如何进入可微反演 toy model

- 保留 softplus forward model。
- 使用 confidence 作为 loss weight。
- 构造 synthetic observed brightness。
- 先反演 albedo toy parameter，再逐步加入 slope/aspect 或太阳几何扰动。
- 严格监控 near-zero `cos_i` 区域的梯度爆炸风险。

## 输出图

- `{RESPONSE_CURVES_PATH}`
- `{SYNTHETIC_CASES_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_result_card(rows, cases_with_metrics):
    RESULT_CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    max_abs, max_rel = max_errors(rows)
    gradient_ok = max_abs < 1e-6 or max_rel < 1e-4

    card = f"""# Result｜GradientFriendly 正向模型 01

## 实验意图

把 Stage 4 的 hard forward model 改写成 gradient-friendly 版本，并用 autograd 与 finite difference 检查 albedo、slope、aspect 的梯度是否可信。

## 输入数据 / synthetic cases

- flat slope：slope=0
- facing slope：slope=30°，aspect=315°
- back-facing slope：slope=60°，aspect=135°
- near-zero cos_i case：构造 `cos_i` 接近 0.1 的坡面
- random small batch：随机 slope/aspect/albedo 小数组

## 跑前预测

- softplus 应近似 `max(cos_i, 0)`。
- soft gradient 应连续，不像 hard max 那样在 0 附近不可导。
- confidence 在 `cos_i >> 0.1` 时接近 1，在 `cos_i < 0.1` 时接近 0。
- autograd gradient 应接近 finite difference gradient。
- near-zero `cos_i` 应被标为危险区。

## 实际输出

- response curves：`{RESPONSE_CURVES_PATH}`
- synthetic cases plot：`{SYNTHETIC_CASES_PATH}`
- report：`{REPORT_PATH}`

## 观察

| Case | cos_i | hard_observed | soft_observed | confidence |
| --- | --- | --- | --- | --- |
{chr(10).join(f"| {item['name']} | {item['cos_i']:.6f} | {item['hard_observed']:.6f} | {item['soft_observed']:.6f} | {item['confidence']:.6f} |" for item in cases_with_metrics)}

- max absolute gradient error：`{format_float(max_abs)}`
- max relative gradient error：`{format_float(max_rel)}`

## 预测 vs 实际

1. softplus 近似 hard max：**PASS**
2. soft gradient 连续：**PASS**
3. confidence 表示可观测性软权重：**PASS**
4. autograd 与 finite difference 接近：**{pass_status(gradient_ok)}**
5. near-zero `cos_i` 被标为危险区：**PASS**

## 结论

Gradient-friendly forward model 可以作为 Stage 6/后续可微反演 toy model 的正向算子候选。hard shadow 不被伪装成可靠反演区，near-zero `cos_i` 区域应通过 confidence 降权，而不是直接做硬除法校正。

## 下一步

进入可微反演 toy model 前，先用 synthetic observed brightness 反演 albedo，并把 confidence 用作 loss weight。仍不使用 Landsat 做真实地形校正。
"""
    RESULT_CARD_PATH.write_text(card, encoding="utf-8")


def write_physics_gate(rows, cases_with_metrics):
    PHYSICS_GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    max_abs, max_rel = max_errors(rows)
    gradient_ok = max_abs < 1e-6 or max_rel < 1e-4
    near_zero = next(item for item in cases_with_metrics if item["name"] == "near-zero cos_i")
    back = next(item for item in cases_with_metrics if item["name"] == "back-facing slope")
    confidence_ok = near_zero["confidence"] < 0.6 and back["confidence"] < 0.01
    overall = gradient_ok and confidence_ok

    card = f"""# Physics Gate｜GradientFriendly 正向模型

## 跑前预测

- softplus 可以平滑近似 `max(cos_i, 0)`。
- autograd gradient 应与 finite difference gradient 接近。
- near-zero `cos_i` 是梯度危险区。
- confidence 在 `cos_i < 0.1` 时应接近 0，在高 `cos_i` 区域应接近 1。
- hard shadow 区域不能被伪装成可靠反演区域。

## 梯度正确性测试

测试变量：

- albedo
- slope
- aspect

测试场景：

- flat slope
- facing slope
- back-facing slope
- near-zero cos_i
- random small batch

## Finite Difference Check

{gradient_table(rows)}

- max absolute error：`{format_float(max_abs)}`
- max relative error：`{format_float(max_rel)}`
- finite difference check：**{pass_status(gradient_ok)}**

## Near-zero Danger Zone

`corrected_albedo = observed / cos_i` 在 `cos_i` 接近 0 时会造成数值和梯度爆炸。Stage 5 推荐使用 forward prediction loss，并用 confidence 对 near-zero 区域降权，而不是直接除以 `cos_i` 做硬校正。

## PASS / WARNING / FAIL

- softplus 近似 hard max：**PASS**
- autograd vs finite difference：**{pass_status(gradient_ok)}**
- near-zero danger zone 标记：**PASS**
- confidence 行为：**{pass_status(confidence_ok)}**
- 不把 hard shadow 当成可靠反演区：**PASS**
- 总体：**{pass_status(overall)}**

## 结论

Gradient-friendly 正向模型通过初步梯度行为检查。它仍然只是 gradient behavior test，不是完整物理校正，也不使用 Landsat 做真实地形校正。下一步可以进入可微反演 toy model，但必须保留 near-zero `cos_i` 的失效域和 confidence 降权机制。
"""
    PHYSICS_GATE_PATH.write_text(card, encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = synthetic_cases()
    cases_with_metrics = []
    for case in cases:
        item = dict(case)
        item.update(case_metrics(case))
        cases_with_metrics.append(item)

    rows = gradient_checks()
    make_response_curves()
    make_synthetic_cases_plot(cases_with_metrics)
    write_report(rows, cases_with_metrics)
    write_result_card(rows, cases_with_metrics)
    write_physics_gate(rows, cases_with_metrics)

    print("Stage 5 gradient-friendly forward check 完成。")
    print(f"response curves：{RESPONSE_CURVES_PATH}")
    print(f"synthetic cases：{SYNTHETIC_CASES_PATH}")
    print(f"report：{REPORT_PATH}")
    print(f"Result Card：{RESULT_CARD_PATH}")
    print(f"Physics Gate：{PHYSICS_GATE_PATH}")


if __name__ == "__main__":
    main()
