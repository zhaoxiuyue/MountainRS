"""
Stage 6 可微反演 Toy Model + 置信度字段

本脚本只做 synthetic differentiable inversion toy：
- 不使用真实 Landsat 做地形校正
- 不改写 Stage 2 / Stage 3 / Stage 4 / Stage 5 数据
- 不进入复杂 BRDF 或真实反演

运行方式：
python3 stage6_differentiable_inversion_toy/scripts/differentiable_albedo_inversion_toy.py
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
    raise SystemExit("缺少 PyTorch。请先运行：python -m pip install torch") from exc


OUTPUT_DIR = ROOT_DIR / "outputs"
REPORT_PATH = ROOT_DIR / "reports" / "differentiable_albedo_inversion_toy_report.md"
RESULT_CARD_PATH = ROOT_DIR / "obsidian_drafts" / "Result_可微反演ToyModel_01.md"
PHYSICS_GATE_PATH = ROOT_DIR / "obsidian_drafts" / "Physics_Gate_可微反演ToyModel.md"
LOSS_CURVES_PATH = OUTPUT_DIR / "inversion_loss_curves.png"
SUMMARY_PATH = OUTPUT_DIR / "inversion_summary.png"

DTYPE = torch.float64
SOFTPLUS_K = 50.0
CONFIDENCE_TAU = 0.1
CONFIDENCE_K = 30.0
TRUE_ALBEDO = 0.3
EPS = 1e-8
OPTIM_STEPS = 900
LEARNING_RATE = 0.08


def logit(value):
    value = torch.tensor(value, dtype=DTYPE)
    return torch.log(value / (1.0 - value))


def soft_illumination(cos_i):
    k = torch.tensor(SOFTPLUS_K, dtype=DTYPE)
    return torch.nn.functional.softplus(k * cos_i) / k


def confidence_weight(cos_i):
    k_conf = torch.tensor(CONFIDENCE_K, dtype=DTYPE)
    tau = torch.tensor(CONFIDENCE_TAU, dtype=DTYPE)
    return torch.sigmoid(k_conf * (cos_i - tau))


def forward_model(albedo, cos_i):
    return albedo * soft_illumination(cos_i)


def synthetic_cases():
    return [
        {
            "name": "well_observed_case",
            "cos_i": [0.5, 0.7, 0.9],
            "true_albedo": TRUE_ALBEDO,
            "noise_std": 0.0,
            "prediction": "albedo_hat 接近 0.3，confidence 高，uncertainty 低。",
        },
        {
            "name": "near_zero_case",
            "cos_i": [0.08, 0.1, 0.12],
            "true_albedo": TRUE_ALBEDO,
            "noise_std": 0.0,
            "prediction": "可能拟合出数值，但 confidence 中低，uncertainty 升高。",
        },
        {
            "name": "shadow_case",
            "cos_i": [-0.3, -0.1, 0.02],
            "true_albedo": TRUE_ALBEDO,
            "noise_std": 0.0,
            "prediction": "反演不可可靠，必须标记为 low observability / unreliable。",
        },
        {
            "name": "sparse_observation_case",
            "cos_i": [0.65, 0.72],
            "true_albedo": TRUE_ALBEDO,
            "noise_std": 0.0,
            "prediction": "可能估得准，但观测数量少，uncertainty 高于 well_observed。",
        },
        {
            "name": "noisy_case",
            "cos_i": [0.4, 0.6, 0.8, 0.9],
            "true_albedo": TRUE_ALBEDO,
            "noise_std": 0.02,
            "prediction": "albedo_hat 接近但不完全等于 0.3，residual 和 uncertainty 上升。",
        },
    ]


def reliability_label(mean_confidence, effective_count, residual_std):
    if mean_confidence < 0.2 or effective_count < 0.75:
        return "LOW"
    if mean_confidence >= 0.85 and effective_count >= 2.5 and residual_std <= 0.012:
        return "HIGH"
    return "MEDIUM"


def uncertainty_proxy(residual_std, mean_confidence, effective_count):
    near_zero_penalty = 1.0 - mean_confidence
    sparse_penalty = max(0.0, 3.0 - effective_count) / 3.0
    residual_term = residual_std / np.sqrt(effective_count + EPS)
    return residual_term + near_zero_penalty + sparse_penalty


def invert_case(case, seed=1234):
    cos_i = torch.tensor(case["cos_i"], dtype=DTYPE)
    true_albedo = torch.tensor(case["true_albedo"], dtype=DTYPE)
    illumination = soft_illumination(cos_i)
    confidence = confidence_weight(cos_i)

    observed = forward_model(true_albedo, cos_i).detach()
    if case["noise_std"] > 0:
        generator = torch.Generator().manual_seed(seed)
        noise = torch.randn(observed.shape, generator=generator, dtype=DTYPE) * case["noise_std"]
        observed = observed + noise

    raw_param = logit(0.1).clone().detach().requires_grad_(True)
    optimizer = torch.optim.Adam([raw_param], lr=LEARNING_RATE)
    losses = []

    for _ in range(OPTIM_STEPS):
        optimizer.zero_grad()
        albedo = torch.sigmoid(raw_param)
        predicted = forward_model(albedo, cos_i)
        loss = torch.mean(confidence * (predicted - observed) ** 2)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))

    with torch.no_grad():
        albedo_hat = torch.sigmoid(raw_param)
        predicted = forward_model(albedo_hat, cos_i)
        residual = predicted - observed
        final_loss = torch.mean(confidence * residual**2)
        residual_std = torch.std(residual, unbiased=False)
        mean_confidence = torch.mean(confidence)
        min_confidence = torch.min(confidence)
        effective_count = torch.sum(confidence)
        abs_error = torch.abs(albedo_hat - true_albedo)

    mean_confidence_f = float(mean_confidence)
    effective_count_f = float(effective_count)
    residual_std_f = float(residual_std)
    uncertainty = uncertainty_proxy(residual_std_f, mean_confidence_f, effective_count_f)
    label = reliability_label(mean_confidence_f, effective_count_f, residual_std_f)

    return {
        "name": case["name"],
        "cos_i": list(case["cos_i"]),
        "true_albedo": float(true_albedo),
        "noise_std": float(case["noise_std"]),
        "prediction": case["prediction"],
        "albedo_hat": float(albedo_hat),
        "absolute_error": float(abs_error),
        "final_loss": float(final_loss),
        "mean_confidence": mean_confidence_f,
        "min_confidence": float(min_confidence),
        "effective_observation_count": effective_count_f,
        "residual_std": residual_std_f,
        "uncertainty_proxy": float(uncertainty),
        "reliability_label": label,
        "soft_illumination": [float(v) for v in illumination],
        "observed": [float(v) for v in observed],
        "predicted": [float(v) for v in predicted],
        "confidence": [float(v) for v in confidence],
        "losses": losses,
    }


def run_inversions():
    return [invert_case(case, seed=1234 + idx) for idx, case in enumerate(synthetic_cases())]


def make_loss_curves(results):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 6))
    for result in results:
        losses = np.asarray(result["losses"], dtype=float)
        ax.plot(np.arange(1, len(losses) + 1), losses + 1e-16, label=result["name"], linewidth=2)
    ax.set_yscale("log")
    ax.set_xlabel("optimization step")
    ax.set_ylabel("weighted forward prediction loss")
    ax.set_title("Stage 6 Synthetic Albedo Inversion Loss Curves")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    plt.tight_layout()
    fig.savefig(LOSS_CURVES_PATH, dpi=150)
    plt.close(fig)


def make_summary_plot(results):
    names = [item["name"] for item in results]
    x = np.arange(len(names))
    albedo_true = [item["true_albedo"] for item in results]
    albedo_hat = [item["albedo_hat"] for item in results]
    mean_conf = [item["mean_confidence"] for item in results]
    uncertainty = [item["uncertainty_proxy"] for item in results]

    fig, axes = plt.subplots(2, 2, figsize=(15, 9))

    width = 0.36
    axes[0, 0].bar(x - width / 2, albedo_true, width=width, label="true albedo")
    axes[0, 0].bar(x + width / 2, albedo_hat, width=width, label="inverted albedo")
    axes[0, 0].set_title("Albedo True vs Hat")
    axes[0, 0].set_ylabel("albedo")
    axes[0, 0].set_ylim(0, 0.5)
    axes[0, 0].legend()

    axes[0, 1].bar(x, mean_conf)
    axes[0, 1].set_title("Mean Observability Confidence")
    axes[0, 1].set_ylabel("confidence")
    axes[0, 1].set_ylim(0, 1.05)

    axes[1, 0].bar(x, uncertainty)
    axes[1, 0].set_title("Uncertainty Proxy")
    axes[1, 0].set_ylabel("proxy value")

    axes[1, 1].axis("off")
    rows = [
        [item["name"], item["reliability_label"], f'{item["effective_observation_count"]:.3f}']
        for item in results
    ]
    table = axes[1, 1].table(
        cellText=rows,
        colLabels=["case", "reliability", "effective N"],
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.4)
    axes[1, 1].set_title("Reliability Labels")

    for ax in axes.flat[:3]:
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=25, ha="right", fontsize=8)
        ax.grid(True, axis="y", alpha=0.25)

    plt.tight_layout()
    fig.savefig(SUMMARY_PATH, dpi=150)
    plt.close(fig)


def format_float(value, digits=6):
    return f"{value:.{digits}g}"


def markdown_table(results):
    header = (
        "| case | albedo_true | albedo_hat | abs_error | final_loss | "
        "mean_confidence | effective_count | residual_std | uncertainty_proxy | reliability |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|\n"
    )
    rows = []
    for item in results:
        rows.append(
            "| {name} | {true} | {hat} | {err} | {loss} | {mean_conf} | {eff} | {resid} | {unc} | {label} |".format(
                name=item["name"],
                true=format_float(item["true_albedo"]),
                hat=format_float(item["albedo_hat"]),
                err=format_float(item["absolute_error"]),
                loss=format_float(item["final_loss"]),
                mean_conf=format_float(item["mean_confidence"]),
                eff=format_float(item["effective_observation_count"]),
                resid=format_float(item["residual_std"]),
                unc=format_float(item["uncertainty_proxy"]),
                label=item["reliability_label"],
            )
        )
    return header + "\n".join(rows)


def gate_checks(results):
    by_name = {item["name"]: item for item in results}
    well = by_name["well_observed_case"]
    near_zero = by_name["near_zero_case"]
    shadow = by_name["shadow_case"]
    sparse = by_name["sparse_observation_case"]
    noisy = by_name["noisy_case"]

    checks = [
        {
            "name": "well_observed_case 的 albedo_hat 接近 true_albedo=0.3",
            "status": "PASS" if well["absolute_error"] <= 0.01 else "FAIL",
            "detail": f"absolute_error={well['absolute_error']:.6g}",
        },
        {
            "name": "shadow_case 必须标记为 LOW reliability",
            "status": "PASS" if shadow["reliability_label"] == "LOW" else "FAIL",
            "detail": f"label={shadow['reliability_label']}, mean_confidence={shadow['mean_confidence']:.6g}",
        },
        {
            "name": "near_zero_case 显示较低 confidence 或较高 uncertainty",
            "status": "PASS"
            if near_zero["mean_confidence"] < 0.7
            or near_zero["uncertainty_proxy"] > well["uncertainty_proxy"]
            else "FAIL",
            "detail": f"mean_confidence={near_zero['mean_confidence']:.6g}, uncertainty={near_zero['uncertainty_proxy']:.6g}",
        },
        {
            "name": "sparse_observation_case 体现观测数量少带来的不确定性",
            "status": "PASS" if sparse["uncertainty_proxy"] > well["uncertainty_proxy"] else "FAIL",
            "detail": f"sparse_uncertainty={sparse['uncertainty_proxy']:.6g}, well_uncertainty={well['uncertainty_proxy']:.6g}",
        },
        {
            "name": "noisy_case residual 和 uncertainty 高于无噪声 well_observed_case",
            "status": "PASS"
            if noisy["residual_std"] > well["residual_std"]
            and noisy["uncertainty_proxy"] > well["uncertainty_proxy"]
            else "FAIL",
            "detail": f"noisy_residual={noisy['residual_std']:.6g}, well_residual={well['residual_std']:.6g}",
        },
        {
            "name": "所有 case 输出 confidence 和 uncertainty_proxy",
            "status": "PASS"
            if all("mean_confidence" in item and "uncertainty_proxy" in item for item in results)
            else "FAIL",
            "detail": "每个 case 均包含 mean/min confidence、effective count、uncertainty proxy。",
        },
        {
            "name": "Stage 6.1 是 synthetic inversion toy，不是真实 Landsat 地形校正",
            "status": "PASS",
            "detail": "脚本不读取 Landsat，不改写 Stage 2/3/4/5 数据。",
        },
    ]
    overall = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return checks, overall


def write_report(results, checks, overall):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    case_lines = []
    for item in results:
        case_lines.append(
            "- `{name}`: cos_i={cos_i}, true_albedo={true}, noise_std={noise}. 预测：{prediction}".format(
                name=item["name"],
                cos_i=item["cos_i"],
                true=item["true_albedo"],
                noise=item["noise_std"],
                prediction=item["prediction"],
            )
        )

    check_lines = [
        f"- **{item['status']}** `{item['name']}`：{item['detail']}" for item in checks
    ]

    text = f"""# Stage 6.1｜可微反演 Toy Model + 置信度字段报告

## Stage 6 目标

本阶段构建一个最小可微反演 toy model：已知 synthetic `cos_i` 与 synthetic observed brightness，通过梯度下降反演 `albedo`，同时输出 observability confidence 与 uncertainty proxy。

## 为什么本阶段是 L3 弱闭环

Stage 6 已经从 L2 正向观测算子进入 L3 反演思维：模型不只计算观测亮度，而是用观测亮度反推潜在参数 `albedo`。但它仍然是 synthetic toy，不使用真实 Landsat，不包含真实大气、BRDF、传感器响应、地表异质性或多时相太阳几何，因此只能称为 L3 弱闭环。

## 为什么不用真实 Landsat

当前 Landsat 是 2023-2024 median composite，不是单日观测。单日地形辐射校正需要影像获取时刻的太阳几何、真实地表 BRDF/阴影/大气条件。把 composite 直接塞进单日物理反演会制造假的物理对应关系，所以本阶段只使用 synthetic observed brightness。

## Forward Model 公式

```text
soft_illumination = softplus(k * cos_i) / k
predicted_observed = albedo_param * soft_illumination
k = {SOFTPLUS_K:g}
```

softplus 是 `max(cos_i, 0)` 的 gradient-friendly 近似。它在阴影区会有 smooth leakage，这是数值近似，不是真实物理光照。

## Loss 公式

```text
loss = mean(confidence * (predicted_observed - observed)^2)
```

这里推荐使用 forward prediction loss，而不是把 `corrected_albedo = observed / cos_i` 作为主要可微目标，因为 near-zero `cos_i` 会造成除法和梯度爆炸风险。

## Confidence 公式

```text
confidence = sigmoid(k_conf * (cos_i - tau))
tau = {CONFIDENCE_TAU:g}
k_conf = {CONFIDENCE_K:g}
```

`confidence` 是 observability weight，不是真实地表可靠性，也不是真实云/阴影/BRDF 概率。

## Synthetic Cases

{chr(10).join(case_lines)}

## 反演结果表

{markdown_table(results)}

## 结果解释

- `well_observed_case` 的 `cos_i` 都明显大于 0.1，illumination 稳定，weighted forward loss 对 `albedo` 有清晰约束，因此应高可信。
- `shadow_case` 即使优化器能输出一个 `albedo_hat`，也不代表反演可靠；它的 illumination 与 confidence 极低，属于 low observability / unreliable 区域。
- `sparse_observation_case` 可能数值上估得准，但观测数量少，effective observation count 低于 well-observed，因此不应过度自信。
- `near_zero_case` 位于 `cos_i≈tau` 附近，confidence 中低；如果改用 `observed / cos_i` 的硬校正形式，除法与梯度都会变危险。
- `noisy_case` 加入 synthetic Gaussian noise 后，residual 和 uncertainty proxy 应高于无噪声 well-observed case。
- `uncertainty_proxy = residual_std / sqrt(effective_count + eps) + near_zero_penalty + sparse_penalty` 只是工程 proxy，不是真实贝叶斯后验或置信区间。

## 正确性闸门

{chr(10).join(check_lines)}

## 是否通过 Stage 6.1

**{overall}**。本阶段完成 synthetic differentiable inversion toy，并输出 confidence 与 uncertainty proxy；但它不是完整物理校正，也不是 Landsat 真实地形校正。

## 输出文件

- `{LOSS_CURVES_PATH}`
- `{SUMMARY_PATH}`
- `{REPORT_PATH}`
- `{RESULT_CARD_PATH}`
- `{PHYSICS_GATE_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def write_result_card(results, overall):
    RESULT_CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = f"""# Result｜可微反演 Toy Model 01

## 实验意图

用 Stage 5 的 gradient-friendly forward model 构建最小可微反演闭环：已知 synthetic `cos_i` 和 synthetic observed brightness，通过梯度下降反演 `albedo`，并同时输出 confidence 与 uncertainty proxy。

## 输入数据 / synthetic cases

- `well_observed_case`: `cos_i=[0.5, 0.7, 0.9]`, `true_albedo=0.3`
- `near_zero_case`: `cos_i=[0.08, 0.1, 0.12]`, `true_albedo=0.3`
- `shadow_case`: `cos_i=[-0.3, -0.1, 0.02]`, `true_albedo=0.3`
- `sparse_observation_case`: `cos_i=[0.65, 0.72]`, `true_albedo=0.3`
- `noisy_case`: `cos_i=[0.4, 0.6, 0.8, 0.9]`, `true_albedo=0.3`, `noise_std=0.02`

## 跑前预测

- well-observed 应恢复到接近 `albedo=0.3`，confidence 高，uncertainty 低。
- near-zero case 可能能拟合，但 confidence 应中低，uncertainty 应升高。
- shadow case 不可可靠反演，必须标为 LOW。
- sparse case 可能数值准，但不应过度自信。
- noisy case residual 与 uncertainty 应高于 well-observed。

## 实际输出

{markdown_table(results)}

## 观察

优化器使用 sigmoid parameterization 保证 `albedo` 位于 0-1。所有 case 都输出了 `albedo_hat`、confidence、effective observation count、residual、uncertainty proxy 与 reliability label。

## 预测 vs 实际

预测与实际整体一致。`shadow_case` 被标记为 LOW reliability；`near_zero_case` 与 `sparse_observation_case` 的 uncertainty proxy 高于 well-observed；`noisy_case` 的 residual 与 uncertainty 上升。

## 结论

Stage 6.1 判定为 **{overall}**。这说明 gradient-friendly forward prediction loss 可以支撑最小 synthetic 反演闭环，但 confidence 与 uncertainty 仍是工程字段，不是真实地表概率或贝叶斯后验。

## 下一步

进入 Stage 6 正式收口前，应把 Result / Physics Gate / Concept / Code Template 整理进正式 Obsidian。之后才考虑 Stage 7 或更复杂的可微反演设计。
"""
    RESULT_CARD_PATH.write_text(text, encoding="utf-8")


def write_physics_gate(results, checks, overall):
    PHYSICS_GATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    check_lines = [
        f"- **{item['status']}** `{item['name']}`：{item['detail']}" for item in checks
    ]
    text = f"""# Physics Gate｜可微反演 Toy Model

## 跑前预测

- well-observed case 应恢复 `albedo≈0.3`。
- near-zero case 应显示 confidence 下降或 uncertainty 上升。
- shadow case 即使输出数值，也必须标记为 LOW reliability。
- sparse case 不应因为数值误差小就被判为高可信。
- noisy case 的 residual 与 uncertainty 应高于无噪声 well-observed。

## 反演正确性测试

使用 synthetic observed brightness：

```text
soft_illumination = softplus(k * cos_i) / k
predicted_observed = albedo_param * soft_illumination
loss = mean(confidence * (predicted_observed - observed)^2)
```

`albedo_param` 使用 sigmoid parameterization，保证反演值位于 0-1。

## Confidence 字段检查

`confidence = sigmoid(k_conf * (cos_i - tau))`。它表示可观测性软权重，不是真实地表可靠性，不是真实云/阴影/BRDF 概率。

## Uncertainty Proxy 字段检查

`uncertainty_proxy` 由 residual、effective observation count、near-zero penalty 与 sparse penalty 组合得到。它只是 proxy，不是真实贝叶斯置信区间。

## Shadow / Near-zero / Sparse 失败域

- shadow：`cos_i <= 0` 或大部分 illumination 极弱时，即使能优化出 `albedo_hat`，也不可判可靠。
- near-zero：`cos_i≈0.1` 附近属于除法和梯度危险区。
- sparse：观测数量少时，数值拟合准确也不能过度自信。

## PASS / WARNING / FAIL

{chr(10).join(check_lines)}

## 结论

**{overall}**。Stage 6.1 通过 synthetic differentiable inversion toy 的物理正确性闸门，但它仍不是 Landsat 真实地形校正，也不是完整 BRDF 或真实不确定性建模。
"""
    PHYSICS_GATE_PATH.write_text(text, encoding="utf-8")


def main():
    for directory in [OUTPUT_DIR, REPORT_PATH.parent, RESULT_CARD_PATH.parent]:
        directory.mkdir(parents=True, exist_ok=True)

    results = run_inversions()
    checks, overall = gate_checks(results)
    make_loss_curves(results)
    make_summary_plot(results)
    write_report(results, checks, overall)
    write_result_card(results, overall)
    write_physics_gate(results, checks, overall)

    print(f"Stage 6.1 overall: {overall}")
    print(f"Report: {REPORT_PATH}")
    print(f"Loss curves: {LOSS_CURVES_PATH}")
    print(f"Summary plot: {SUMMARY_PATH}")
    print(f"Result card: {RESULT_CARD_PATH}")
    print(f"Physics gate: {PHYSICS_GATE_PATH}")


if __name__ == "__main__":
    main()
