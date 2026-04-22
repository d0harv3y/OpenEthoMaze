from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .config import RadialArmControllerConfig

from .config import ram_apothem_cm_from_template, sync_ram_px_per_cm


@dataclass(frozen=True)
class LegacyRadialArmTemplate:
    """Migrated legacy RAM calibration used for raw-video playback and import."""

    px_per_cm: float
    center_px: tuple[float, float]
    template_params: dict[str, float | int]
    center_poly_xy: np.ndarray
    arms_table: np.ndarray
    escape_holes: dict[int, tuple[float, float, float]]


_ARMS_TABLE_DTYPE = np.dtype(
    [
        ("arm_index", np.uint8),
        ("half_index", np.uint8),
        ("x0", np.float32),
        ("y0", np.float32),
        ("x1", np.float32),
        ("y1", np.float32),
        ("x2", np.float32),
        ("y2", np.float32),
        ("x3", np.float32),
        ("y3", np.float32),
    ]
)


LEGACY_RAM_TEMPLATE = LegacyRadialArmTemplate(
    px_per_cm=2.8156093922985836,
    center_px=(322.9999694824219, 239.00001525878906),
    template_params={
        "center_midedge_to_midedge_cm": 86.0,
        "arm_length_cm": 44.0,
        "arm_width_cm": 25.0,
        "arm_split_cm": 21.0,
        "hole_arm_index": 0,
        "hole_radius_cm": 3.0,
        "hole_inset_from_arm_end_cm": 5.0,
    },
    center_poly_xy=np.asarray(
        [
            [299.912109375, 120.32234191894531],
            [255.10128784179688, 137.53460693359375],
            [220.62741088867188, 170.19407653808594],
            [201.73883056640625, 213.32861328125],
            [201.31117248535156, 260.37139892578125],
            [219.40953063964844, 304.1605529785156],
            [253.27859497070312, 338.0296325683594],
            [297.7621154785156, 356.82232666015625],
            [346.087890625, 357.67767333984375],
            [390.8987121582031, 340.46539306640625],
            [425.3725891113281, 307.8059387207031],
            [444.26116943359375, 264.67138671875],
            [444.6888427734375, 217.6286163330078],
            [426.5904846191406, 173.8394317626953],
            [392.7214050292969, 139.97036743164062],
            [348.2378845214844, 121.17765808105469],
        ],
        dtype=np.float32,
    ),
    arms_table=np.asarray(
        [
            (0, 0, 288.76251220703125, 120.125, 359.38751220703125, 121.375, 359.9125061035156, 63.625, 289.2875061035156, 62.375),
            (0, 1, 289.2875061035156, 62.375, 359.9125061035156, 63.625, 360.48748779296875, 0.375, 289.86248779296875, -0.875),
            (1, 0, 384.9071960449219, 132.15615844726562, 434.4046630859375, 181.6536407470703, 476.7250061035156, 141.56068420410156, 427.2275390625, 92.0632095336914),
            (1, 1, 427.2275390625, 92.0632095336914, 476.7250061035156, 141.56068420410156, 523.0758666992188, 97.64935302734375, 473.5783996582031, 48.151878356933594),
            (2, 0, 444.7875061035156, 206.77499389648438, 444.1625061035156, 275.5249938964844, 503.48748779296875, 276.57501220703125, 504.11248779296875, 207.8249969482422),
            (2, 1, 504.11248779296875, 207.8249969482422, 503.48748779296875, 276.57501220703125, 568.4625244140625, 277.7250061035156, 569.0875244140625, 208.97500610351562),
            (3, 0, 433.3263244628906, 300.27081298828125, 382.9449768066406, 348.0005187988281, 424.5228576660156, 389.5783996582031, 474.9042053222656, 341.84869384765625),
            (3, 1, 474.9042053222656, 341.84869384765625, 424.5228576660156, 389.5783996582031, 470.060546875, 435.1160583496094, 520.44189453125, 387.3863525390625),
            (4, 0, 357.23748779296875, 357.875, 286.61248779296875, 356.625, 286.0874938964844, 414.375, 356.7124938964844, 415.625),
            (4, 1, 356.7124938964844, 415.625, 286.0874938964844, 414.375, 285.51251220703125, 477.625, 356.13751220703125, 478.875),
            (5, 0, 261.0928039550781, 345.8438415527344, 211.59532165527344, 296.34637451171875, 169.2749786376953, 336.4393005371094, 218.7724609375, 385.9367980957031),
            (5, 1, 218.7724609375, 385.9367980957031, 169.2749786376953, 336.4393005371094, 122.92413330078125, 380.35064697265625, 172.42161560058594, 429.8481140136719),
            (6, 0, 201.21249389648438, 271.2250061035156, 201.83749389648438, 202.47500610351562, 142.5124969482422, 201.4250030517578, 141.8874969482422, 270.17498779296875),
            (6, 1, 141.8874969482422, 270.17498779296875, 142.5124969482422, 201.4250030517578, 77.5374984741211, 200.27499389648438, 76.9124984741211, 269.0249938964844),
            (7, 0, 212.6736602783203, 177.7292022705078, 263.0550231933594, 129.99948120117188, 221.47714233398438, 88.4216079711914, 171.0957794189453, 136.1513214111328),
            (7, 1, 171.0957794189453, 136.1513214111328, 221.47714233398438, 88.4216079711914, 175.93946838378906, 42.883934020996094, 125.55810546875, 90.61363983154297),
        ],
        dtype=_ARMS_TABLE_DTYPE,
    ),
    escape_holes={
        0: (324.9190368652344, 27.904930114746094, 14.078046798706055),
        1: (477.88714599609375, 92.26481628417969, 14.078046798706055),
        2: (540.6233520507812, 242.85174560546875, 14.078046798706055),
        3: (475.34185791015625, 391.34185791015625, 14.078046798706055),
        4: (321.0809631347656, 450.0950622558594, 14.078046798706055),
        5: (168.1128692626953, 385.73516845703125, 14.078046798706055),
        6: (105.37667846679688, 235.14825439453125, 14.078046798706055),
        7: (170.65814208984375, 86.65814971923828, 14.078046798706055),
    },
)


def legacy_escape_hole_xyr(exit_arm_index: int) -> tuple[float, float, float]:
    """Return migrated legacy escape-hole geometry for one exit arm."""
    arm_index = int(max(0, min(7, exit_arm_index)))
    return LEGACY_RAM_TEMPLATE.escape_holes[arm_index]


def apply_legacy_template_config(config: "RadialArmControllerConfig") -> None:
    """Apply the migrated legacy RAM template to a controller config."""
    params = LEGACY_RAM_TEMPLATE.template_params
    template = config.radial_arm.template
    calibration = config.radial_arm.calibration

    template.center_midedge_to_midedge_cm = float(
        params["center_midedge_to_midedge_cm"]
    )
    template.arm_length_cm = float(params["arm_length_cm"])
    template.arm_width_cm = float(params["arm_width_cm"])
    template.arm_split_cm = float(params["arm_split_cm"])
    template.hole_arm_index = int(params["hole_arm_index"])
    template.hole_radius_cm = float(params["hole_radius_cm"])
    template.hole_inset_from_arm_end_cm = float(params["hole_inset_from_arm_end_cm"])

    calibration.template_center_x_px = float(LEGACY_RAM_TEMPLATE.center_px[0])
    calibration.template_center_y_px = float(LEGACY_RAM_TEMPLATE.center_px[1])
    calibration.template_rotation_deg = -90.0
    ap_cm = ram_apothem_cm_from_template(template)
    calibration.apothem_px = float(LEGACY_RAM_TEMPLATE.px_per_cm) * ap_cm
    sync_ram_px_per_cm(config.radial_arm)
