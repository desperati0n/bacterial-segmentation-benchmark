[**English**](README.md) | [简体中文](README.zh-CN.md)

# Four-model Bacterial Instance-segmentation Gallery

The gallery compares Cellpose-SAM `cpsam_v2`, Omnipose `bact_phase_omnitorch_0`, Omnipose `bact_fluor_omnitorch_0`, and the MicroSAM DeepBacs Specialist (ViT-L + AIS decoder).

Each image is a 2×5 panel containing the source image, four full-image model overlays, and the corresponding center 128×128 crops. Both Omnipose weights were run with the configured two-channel input.

`GT_*` files use samples with human-reference masks. `GEN_*` files cover general or deliberately selected failure scenarios. Files beginning with `image*` retain the historical gallery naming used during the study.
