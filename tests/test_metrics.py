import numpy as np
import pytest

from bacterial_segmentation_benchmark import compute_instance_segmentation_metrics


def test_perfect_two_instance_prediction() -> None:
    labels = np.zeros((12, 12), dtype=np.uint16)
    labels[1:5, 1:5] = 1
    labels[7:11, 7:11] = 8

    metrics = compute_instance_segmentation_metrics(labels, labels.copy())

    assert metrics["n_gt"] == 2
    assert metrics["n_pred"] == 2
    assert metrics["ap_50"] == 1.0
    assert metrics["ap_75"] == 1.0
    assert metrics["fg_dice"] == 1.0
    assert metrics["boundary_f1"] == 1.0


def test_empty_prediction_is_counted_as_missed_instances() -> None:
    ground_truth = np.zeros((8, 8), dtype=np.uint16)
    ground_truth[2:6, 2:6] = 1
    prediction = np.zeros_like(ground_truth)

    metrics = compute_instance_segmentation_metrics(ground_truth, prediction)

    assert metrics["fn_50"] == 1
    assert metrics["fp_50"] == 0
    assert metrics["ap_50"] == 0.0
    assert metrics["rel_count_error"] == 1.0


def test_shape_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="same shape"):
        compute_instance_segmentation_metrics(
            np.zeros((4, 4), dtype=np.uint8),
            np.zeros((5, 5), dtype=np.uint8),
        )


def test_non_integer_labels_are_rejected() -> None:
    with pytest.raises(TypeError, match="integer dtype"):
        compute_instance_segmentation_metrics(
            np.zeros((4, 4), dtype=np.float32),
            np.zeros((4, 4), dtype=np.uint8),
        )
