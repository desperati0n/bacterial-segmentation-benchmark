"""Metrics used by the bacterial microscopy segmentation benchmark."""

from __future__ import annotations

from typing import Any

import numpy as np
import scipy.ndimage as ndi


def compute_instance_segmentation_metrics(
    ground_truth: np.ndarray,
    prediction: np.ndarray,
    *,
    boundary_tolerance: float = 2.0,
) -> dict[str, Any]:
    """Compare two 2-D integer instance-label images.

    Label ``0`` is background; each positive integer identifies one instance.
    Matching is greedy by descending IoU and one-to-one at each threshold.
    ``ap_50`` and ``ap_75`` follow the instance-segmentation convention
    ``TP / (TP + FP + FN)`` used in the original study.
    """
    ground_truth = _validate_label_image("ground_truth", ground_truth)
    prediction = _validate_label_image("prediction", prediction)
    if ground_truth.shape != prediction.shape:
        raise ValueError(
            "ground_truth and prediction must have the same shape; "
            f"got {ground_truth.shape} and {prediction.shape}"
        )

    gt_dense, n_gt = _dense_labels(ground_truth)
    pred_dense, n_pred = _dense_labels(prediction)

    if n_gt == 0 and n_pred == 0:
        return _empty_result()

    gt_fg = gt_dense > 0
    pred_fg = pred_dense > 0
    foreground = _foreground_metrics(gt_fg, pred_fg)

    if n_gt == 0 or n_pred == 0:
        return {
            "n_gt": n_gt,
            "n_pred": n_pred,
            "abs_count_error": abs(n_pred - n_gt),
            "rel_count_error": 1.0 if n_gt else 0.0,
            **_no_match_metrics(n_gt, n_pred),
            **foreground,
            "boundary_precision": 0.0,
            "boundary_recall": 0.0,
            "boundary_f1": 0.0,
            "split_count": 0,
            "merge_count": 0,
        }

    confusion = np.bincount(
        (gt_dense.ravel() * (n_pred + 1) + pred_dense.ravel()),
        minlength=(n_gt + 1) * (n_pred + 1),
    ).reshape(n_gt + 1, n_pred + 1)

    intersections = confusion[1:, 1:].astype(np.float64)
    gt_areas = confusion[1:, :].sum(axis=1, keepdims=True).astype(np.float64)
    pred_areas = confusion[:, 1:].sum(axis=0, keepdims=True).astype(np.float64)
    unions = gt_areas + pred_areas - intersections
    iou = np.divide(
        intersections,
        unions,
        out=np.zeros_like(intersections),
        where=unions > 0,
    )

    match_50 = _match_at_threshold(iou, 0.50, n_gt, n_pred)
    match_75 = _match_at_threshold(iou, 0.75, n_gt, n_pred)
    boundary = _boundary_metrics(gt_fg, pred_fg, boundary_tolerance)

    pred_fraction = intersections / np.maximum(pred_areas, 1.0)
    gt_fraction = intersections / np.maximum(gt_areas, 1.0)
    significant_overlap = (pred_fraction > 0.15) & (gt_fraction > 0.10)

    absolute_count_error = abs(n_pred - n_gt)
    return {
        "n_gt": n_gt,
        "n_pred": n_pred,
        "abs_count_error": absolute_count_error,
        "rel_count_error": round(absolute_count_error / n_gt, 4),
        **{f"{key}_50": value for key, value in match_50.items()},
        **{f"{key}_75": value for key, value in match_75.items()},
        **foreground,
        **boundary,
        "split_count": int(np.sum(significant_overlap.sum(axis=1) >= 2)),
        "merge_count": int(np.sum(significant_overlap.sum(axis=0) >= 2)),
    }


def _validate_label_image(name: str, image: np.ndarray) -> np.ndarray:
    image = np.asarray(image)
    if image.ndim != 2:
        raise ValueError(f"{name} must be a 2-D label image; got {image.ndim} dimensions")
    if not np.issubdtype(image.dtype, np.integer):
        raise TypeError(f"{name} must use an integer dtype; got {image.dtype}")
    if np.any(image < 0):
        raise ValueError(f"{name} contains negative labels")
    return image


def _dense_labels(image: np.ndarray) -> tuple[np.ndarray, int]:
    labels = np.unique(image)
    labels = labels[labels > 0]
    lookup = np.zeros(int(image.max(initial=0)) + 1, dtype=np.int32)
    lookup[labels] = np.arange(1, len(labels) + 1, dtype=np.int32)
    return lookup[image], len(labels)


def _foreground_metrics(gt: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    intersection = int(np.logical_and(gt, pred).sum())
    union = int(np.logical_or(gt, pred).sum())
    total = int(gt.sum() + pred.sum())
    return {
        "fg_iou": round(intersection / union, 4) if union else 1.0,
        "fg_dice": round(2 * intersection / total, 4) if total else 1.0,
    }


def _match_at_threshold(
    iou: np.ndarray,
    threshold: float,
    n_gt: int,
    n_pred: int,
) -> dict[str, float | int]:
    rows, columns = np.where(iou >= threshold)
    candidates = sorted(
        ((float(iou[row, column]), int(row), int(column)) for row, column in zip(rows, columns)),
        reverse=True,
    )
    matched_gt: set[int] = set()
    matched_pred: set[int] = set()
    for _, row, column in candidates:
        if row not in matched_gt and column not in matched_pred:
            matched_gt.add(row)
            matched_pred.add(column)

    true_positive = len(matched_gt)
    false_positive = n_pred - true_positive
    false_negative = n_gt - true_positive
    denominator = true_positive + false_positive + false_negative
    return {
        "tp": true_positive,
        "fp": false_positive,
        "fn": false_negative,
        "ap": round(true_positive / denominator, 4) if denominator else 0.0,
        "precision": round(true_positive / n_pred, 4) if n_pred else 0.0,
        "recall": round(true_positive / n_gt, 4) if n_gt else 0.0,
    }


def _boundary_metrics(
    gt: np.ndarray,
    pred: np.ndarray,
    tolerance: float,
) -> dict[str, float]:
    structure = ndi.generate_binary_structure(2, 2)
    gt_boundary = gt ^ ndi.binary_erosion(gt, structure=structure)
    pred_boundary = pred ^ ndi.binary_erosion(pred, structure=structure)
    if not np.any(gt_boundary) and not np.any(pred_boundary):
        return {"boundary_precision": 1.0, "boundary_recall": 1.0, "boundary_f1": 1.0}
    if not np.any(gt_boundary) or not np.any(pred_boundary):
        return {"boundary_precision": 0.0, "boundary_recall": 0.0, "boundary_f1": 0.0}

    distance_to_gt = ndi.distance_transform_edt(~gt_boundary)
    distance_to_pred = ndi.distance_transform_edt(~pred_boundary)
    precision = float(np.mean(distance_to_gt[pred_boundary] <= tolerance))
    recall = float(np.mean(distance_to_pred[gt_boundary] <= tolerance))
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "boundary_precision": round(precision, 4),
        "boundary_recall": round(recall, 4),
        "boundary_f1": round(f1, 4),
    }


def _no_match_metrics(n_gt: int, n_pred: int) -> dict[str, float | int]:
    result: dict[str, float | int] = {}
    for suffix in ("50", "75"):
        result.update(
            {
                f"tp_{suffix}": 0,
                f"fp_{suffix}": n_pred,
                f"fn_{suffix}": n_gt,
                f"ap_{suffix}": 0.0,
                f"precision_{suffix}": 0.0,
                f"recall_{suffix}": 0.0,
            }
        )
    return result


def _empty_result() -> dict[str, float | int]:
    return {
        "n_gt": 0,
        "n_pred": 0,
        "abs_count_error": 0,
        "rel_count_error": 0.0,
        "tp_50": 0,
        "fp_50": 0,
        "fn_50": 0,
        "ap_50": 1.0,
        "precision_50": 1.0,
        "recall_50": 1.0,
        "tp_75": 0,
        "fp_75": 0,
        "fn_75": 0,
        "ap_75": 1.0,
        "precision_75": 1.0,
        "recall_75": 1.0,
        "fg_iou": 1.0,
        "fg_dice": 1.0,
        "boundary_precision": 1.0,
        "boundary_recall": 1.0,
        "boundary_f1": 1.0,
        "split_count": 0,
        "merge_count": 0,
    }
