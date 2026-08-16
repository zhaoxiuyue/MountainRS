#!/usr/bin/env python3
"""几何失效传播：版本判定、变更分类与标记传播。

规则取自 configs/geometry-version-and-propagation-v1.json，本模块只实现，
不定义——规则在 fixture 运行之前已冻结。

核心：几何版本按「值 + 消费者影响半径」判定。artifact 身份只是载体。
同一次几何变更对不同影响半径的消费者可以得出不同结论，这是设计意图。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np

CONTAINER = Path(__file__).resolve().parents[1]
RULES_PATH = CONTAINER / "configs/geometry-version-and-propagation-v1.json"

VALID = "valid"
INVALIDATED = "invalidated"
QUARANTINED = "quarantined"

ARTIFACT_ONLY = "artifact_only"
VALUE_CHANGE_IN_SCOPE = "value_change_in_scope"
SCOPE_EXTENSION = "scope_extension"


class UnregisteredConsumer(Exception):
    """未登记的几何消费者。默认半径 0 会系统性产生假阴性，故一律停机。"""


class CacheVersionMismatch(Exception):
    """cache 携带的 geometry version 与当前不符。禁止静默重算。"""


def load_rules() -> dict[str, Any]:
    with RULES_PATH.open(encoding="utf-8") as stream:
        return json.load(stream)


@dataclass(frozen=True)
class Grid:
    """轴对齐栅格的地理参照。origin 为左上角，y 向下递减。"""
    origin_x: float
    origin_y: float
    resolution: float
    width: int
    height: int

    def bounds(self) -> tuple[float, float, float, float]:
        return (self.origin_x,
                self.origin_y - self.height * self.resolution,
                self.origin_x + self.width * self.resolution,
                self.origin_y)

    def window_for(self, left: float, bottom: float, right: float, top: float):
        """返回覆盖给定世界坐标矩形的行列切片；越界部分被裁剪。"""
        c0 = int(np.floor((left - self.origin_x) / self.resolution))
        c1 = int(np.ceil((right - self.origin_x) / self.resolution))
        r0 = int(np.floor((self.origin_y - top) / self.resolution))
        r1 = int(np.ceil((self.origin_y - bottom) / self.resolution))
        return (slice(max(r0, 0), min(r1, self.height)),
                slice(max(c0, 0), min(c1, self.width)))

    def contains_rect(self, left: float, bottom: float, right: float, top: float) -> bool:
        bl, bb, br, bt = self.bounds()
        return left >= bl - 1e-9 and bottom >= bb - 1e-9 and right <= br + 1e-9 and top <= bt + 1e-9


@dataclass(frozen=True)
class Geometry:
    """一份几何数据：值 + 参照 + artifact 身份。"""
    artifact_id: str
    values: np.ndarray
    grid: Grid

    def artifact_hash(self) -> str:
        return hashlib.sha256(np.ascontiguousarray(self.values).tobytes()).hexdigest()

    def read_rect(self, left: float, bottom: float, right: float, top: float) -> np.ndarray:
        rows, cols = self.grid.window_for(left, bottom, right, top)
        return self.values[rows, cols]


@dataclass
class Artifact:
    id: str
    kind: str                       # geometry_consumer | derived | observation
    depends_on: list[str] = field(default_factory=list)
    consumer_name: str | None = None    # 仅 geometry_consumer 需要


class DependencyGraph:
    def __init__(self, artifacts: Iterable[Artifact]):
        self.nodes: dict[str, Artifact] = {a.id: a for a in artifacts}
        for a in self.nodes.values():
            for dep in a.depends_on:
                if dep not in self.nodes:
                    raise ValueError(f"依赖 {dep} 未登记（来自 {a.id}）")

    def direct_dependents_of(self, artifact_id: str) -> list[str]:
        return sorted(a.id for a in self.nodes.values() if artifact_id in a.depends_on)

    def descendants_of(self, roots: Iterable[str]) -> list[str]:
        """roots 的传递后代，不含 roots 自身。"""
        seen: set[str] = set()
        frontier = list(roots)
        while frontier:
            current = frontier.pop()
            for dependent in self.direct_dependents_of(current):
                if dependent not in seen:
                    seen.add(dependent)
                    frontier.append(dependent)
        return sorted(seen - set(roots))

    def path_from(self, source: str, target: str) -> list[str] | None:
        """返回一条 source → target 的依赖路径，用于 manifest 的 propagation_path。"""
        stack = [(source, [source])]
        visited = set()
        while stack:
            node, path = stack.pop()
            if node == target:
                return path
            if node in visited:
                continue
            visited.add(node)
            for dependent in self.direct_dependents_of(node):
                stack.append((dependent, path + [dependent]))
        return None


class ConsumerRegistry:
    def __init__(self, rules: dict[str, Any]):
        self._radii: dict[str, float] = {
            e["consumer"]: float(e["influence_radius_m"])
            for e in rules["consumer_registry"]["entries"]
        }

    def radius(self, consumer: str) -> float:
        if consumer not in self._radii:
            raise UnregisteredConsumer(
                f"消费者 {consumer!r} 未在 consumer_registry 登记。"
                f"规则要求 fail closed——默认半径 0 会系统性产生假阴性失效。")
        return self._radii[consumer]

    def known(self) -> list[str]:
        return sorted(self._radii)


def influence_rect(compute_rect: tuple[float, float, float, float],
                   radius_m: float) -> tuple[float, float, float, float]:
    """消费者的影响域 = 其计算范围向外扩张影响半径。"""
    left, bottom, right, top = compute_rect
    return (left - radius_m, bottom - radius_m, right + radius_m, top + radius_m)


def classify_change(old: Geometry, new: Geometry, consumer: str,
                    compute_rect: tuple[float, float, float, float],
                    registry: ConsumerRegistry,
                    consumer_had_prior_output: bool = True) -> dict[str, Any]:
    """对单个消费者判定几何变更类别。"""
    radius = registry.radius(consumer)
    rect = influence_rect(compute_rect, radius)
    detail: dict[str, Any] = {
        "consumer": consumer,
        "influence_radius_m": radius,
        "influence_rect": list(rect),
        "old_artifact_hash": old.artifact_hash()[:16],
        "new_artifact_hash": new.artifact_hash()[:16],
    }

    old_covers = old.grid.contains_rect(*rect)
    new_covers = new.grid.contains_rect(*rect)

    if not old_covers and new_covers:
        # 覆盖扩大：此前该消费者的影响域伸出旧数据之外
        detail.update({
            "change_class": SCOPE_EXTENSION,
            "old_covers_influence_rect": False,
            "consumer_had_prior_output": consumer_had_prior_output,
            "reason": ("影响域伸出旧覆盖之外。此前若有产出，该产出建立在被截断的搜索域上，"
                       "故失效；此前若无产出，属新增能力，不涉及失效。"),
        })
        return detail

    if not new_covers:
        detail.update({
            "change_class": SCOPE_EXTENSION,
            "new_covers_influence_rect": False,
            "reason": "新几何未覆盖该消费者的影响域，无法在其上计算。",
            "insufficient_coverage": True,
        })
        return detail

    old_patch = old.read_rect(*rect)
    new_patch = new.read_rect(*rect)
    if old_patch.shape != new_patch.shape:
        detail.update({
            "change_class": VALUE_CHANGE_IN_SCOPE,
            "reason": f"影响域内栅格形状不一致：{old_patch.shape} vs {new_patch.shape}。",
        })
        return detail

    differing = int(np.count_nonzero(old_patch != new_patch))
    detail["pixels_compared"] = int(old_patch.size)
    detail["pixels_differing"] = differing
    if differing == 0:
        detail.update({
            "change_class": ARTIFACT_ONLY,
            "reason": "影响域内几何值逐元素相等；artifact 身份改变不构成几何版本改变。",
        })
    else:
        detail.update({
            "change_class": VALUE_CHANGE_IN_SCOPE,
            "max_abs_difference": float(np.max(np.abs(
                old_patch.astype("float64") - new_patch.astype("float64")))),
            "reason": f"影响域内 {differing} 个像元的几何值发生变化。",
        })
    return detail


def propagate(graph: DependencyGraph, geometry_artifact_id: str,
              per_consumer: list[dict[str, Any]]) -> dict[str, Any]:
    """按逐消费者的变更分类结果生成标记与 manifest。"""
    marks: dict[str, str] = {aid: VALID for aid in graph.nodes}
    reasons: dict[str, str] = {}
    invalidated_roots: list[str] = []

    consumer_to_artifact = {a.consumer_name: a.id for a in graph.nodes.values()
                            if a.consumer_name}

    for verdict in per_consumer:
        consumer = verdict["consumer"]
        artifact_id = consumer_to_artifact.get(consumer)
        if artifact_id is None:
            continue
        cls = verdict["change_class"]
        if cls == ARTIFACT_ONLY:
            continue
        if cls == SCOPE_EXTENSION and not verdict.get("consumer_had_prior_output", True):
            continue    # 此前无产出，属新增能力
        marks[artifact_id] = INVALIDATED
        reasons[artifact_id] = f"{cls}: {verdict['reason']}"
        invalidated_roots.append(artifact_id)

    for descendant in graph.descendants_of(invalidated_roots):
        if marks[descendant] == VALID:
            marks[descendant] = QUARANTINED
            reasons[descendant] = ("descendant_of_invalidated: 上游被判失效，本 artifact 的值"
                                   "是否改变尚未确定，须在上游重算后重新评估。")

    paths = {}
    for aid, mark in marks.items():
        if mark == VALID:
            continue
        for root in invalidated_roots:
            path = graph.path_from(root, aid) if aid != root else [root]
            if path:
                paths[aid] = path
                break

    return {
        "change_source": {"geometry_artifact_id": geometry_artifact_id},
        "per_consumer_verdict": per_consumer,
        "marks": dict(sorted(marks.items())),
        "reason_codes": dict(sorted(reasons.items())),
        "propagation_path": dict(sorted(paths.items())),
        "unaffected_artifacts": sorted(a for a, m in marks.items() if m == VALID),
        "counts": {
            INVALIDATED: sum(1 for m in marks.values() if m == INVALIDATED),
            QUARANTINED: sum(1 for m in marks.values() if m == QUARANTINED),
            VALID: sum(1 for m in marks.values() if m == VALID),
        },
    }


def geometry_version_digest(geom: Geometry, consumer: str,
                            compute_rect: tuple[float, float, float, float],
                            registry: ConsumerRegistry) -> str:
    """消费者视角的几何版本摘要：影响域内值的 hash。"""
    rect = influence_rect(compute_rect, registry.radius(consumer))
    patch = geom.read_rect(*rect)
    digest = hashlib.sha256()
    digest.update(consumer.encode())
    digest.update(np.ascontiguousarray(patch).tobytes())
    return digest.hexdigest()


def load_cache_or_fail(cache_entry: dict[str, Any], current_digest: str) -> Any:
    """载入 cache；版本不符即 fail closed。禁止静默回退到重算。"""
    recorded = cache_entry.get("geometry_version_digest")
    if recorded != current_digest:
        raise CacheVersionMismatch(
            f"cache 条目 {cache_entry.get('id')!r} 的 geometry version 摘要为 "
            f"{str(recorded)[:16]}…，当前为 {current_digest[:16]}…。"
            f"禁止静默重算——版本漂移必须被报出。")
    return cache_entry["payload"]


def rollback(marks_before: dict[str, str], receipt: dict[str, Any]) -> dict[str, str]:
    """按 receipt 回到传播前的标记状态。"""
    if receipt.get("marks_before") != marks_before:
        raise ValueError("receipt 记录的传播前状态与给定状态不符，拒绝回滚")
    return dict(receipt["marks_before"])
