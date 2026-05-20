from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from PySide6.QtWidgets import QMessageBox

    HAS_QT = True
except ImportError:
    HAS_QT = False
    QMessageBox = None  # type: ignore[assignment]


PORT_PLACEHOLDER = "— Select port —"


@dataclass
class McConnectionResult:
    stimulus: Any
    button_text: str
    status_label: str
    status_style: str
    status_message: str


def refresh_serial_ports(port_combo, list_ports_module: Any) -> None:
    """Repopulate the COM-port combo box from ``serial.tools.list_ports``."""
    if list_ports_module is None:
        return
    current = port_combo.currentData() or port_combo.currentText()
    port_combo.clear()
    port_combo.addItem(PORT_PLACEHOLDER, "")
    for port in list_ports_module.comports():
        label = f"{port.device}" + (f" ({port.description})" if port.description else "")
        port_combo.addItem(label, port.device)
    idx = port_combo.findData(current)
    if idx >= 0:
        port_combo.setCurrentIndex(idx)
    elif current:
        port_combo.addItem(current, current)
        port_combo.setCurrentIndex(port_combo.count() - 1)


def toggle_mc_connection(
    *,
    current_stimulus: Any,
    arduino_cls: Any,
    port_combo,
    stimulus_config,
    config,
) -> McConnectionResult:
    """Connect or disconnect the MCU and return the desired UI state."""
    if current_stimulus is not None and getattr(current_stimulus, "connected", False):
        current_stimulus.disconnect()
        return McConnectionResult(
            stimulus=current_stimulus,
            button_text="Connect",
            status_label="Disconnected",
            status_style="color: gray;",
            status_message="MC disconnected.",
        )

    port = port_combo.currentData() or (port_combo.currentText().strip() or None)
    if not port or port == PORT_PLACEHOLDER:
        raise ValueError("Select a COM port.")

    stimulus = arduino_cls(
        port=port,
        baud=9600,
        min_duty_pct=stimulus_config.min_duty_pct,
        max_duty_pct=stimulus_config.max_duty_pct,
    )
    if stimulus.connect(port):
        config.arduino_port = port
        return McConnectionResult(
            stimulus=stimulus,
            button_text="Disconnect",
            status_label="Connected",
            status_style="color: green;",
            status_message=f"MC connected on {port}",
        )

    raise RuntimeError(
        "Wrong firmware or no response. Load firmware/vast_controller_duty.ino on the MC."
    )


def flash_firmware(*, parent, dev_mode: bool, port_combo, status_cb) -> None:
    """Compile and upload firmware via ``arduino-cli`` when dev mode is enabled."""
    if not dev_mode:
        return
    cli = shutil.which("arduino-cli")
    if not cli:
        if HAS_QT and QMessageBox is not None:
            QMessageBox.warning(
                parent,
                "Flash firmware",
                "arduino-cli not found. Install from https://arduino.github.io/arduino-cli/ and add it to PATH.",
            )
        return
    port = (port_combo.currentData() or port_combo.currentText() or "").strip()
    if not port or port == PORT_PLACEHOLDER:
        status_cb("Select a COM port first.")
        if HAS_QT and QMessageBox is not None:
            QMessageBox.warning(parent, "Flash firmware", "Select a COM port first.")
        return
    try:
        firmware_dir = (
            Path(__file__).resolve().parent.parent.parent / "firmware" / "vast_controller_duty"
        )
    except Exception:
        firmware_dir = None
    if (
        not firmware_dir
        or not firmware_dir.is_dir()
        or not (firmware_dir / "vast_controller_duty.ino").exists()
    ):
        if HAS_QT and QMessageBox is not None:
            QMessageBox.warning(
                parent,
                "Flash firmware",
                f"Firmware folder not found (expected {firmware_dir} with vast_controller_duty.ino).",
            )
        return

    fqbn = "arduino:avr:uno"
    status_cb("Compiling firmware…")
    try:
        result = subprocess.run(
            [cli, "compile", "--fqbn", fqbn, str(firmware_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        status_cb("Compile timed out.")
        if HAS_QT and QMessageBox is not None:
            QMessageBox.warning(parent, "Flash firmware", "Compile timed out (120 s).")
        return
    except Exception as exc:
        status_cb(f"Compile failed: {exc}")
        if HAS_QT and QMessageBox is not None:
            QMessageBox.warning(parent, "Flash firmware", f"Compile failed: {exc}")
        return
    if result.returncode != 0:
        status_cb("Compile failed.")
        out = (result.stdout or "") + (result.stderr or "")
        if HAS_QT and QMessageBox is not None:
            QMessageBox.warning(
                parent,
                "Flash firmware",
                "Compile failed.\n\n" + (out.strip() or "No output"),
            )
        return

    status_cb("Uploading firmware…")
    try:
        result = subprocess.run(
            [cli, "upload", "-p", port, "--fqbn", fqbn, str(firmware_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        status_cb("Upload timed out.")
        if HAS_QT and QMessageBox is not None:
            QMessageBox.warning(parent, "Flash firmware", "Upload timed out (60 s).")
        return
    except Exception as exc:
        status_cb(f"Upload failed: {exc}")
        if HAS_QT and QMessageBox is not None:
            QMessageBox.warning(parent, "Flash firmware", f"Upload failed: {exc}")
        return
    if result.returncode != 0:
        status_cb("Upload failed.")
        out = (result.stdout or "") + (result.stderr or "")
        if HAS_QT and QMessageBox is not None:
            QMessageBox.warning(
                parent,
                "Flash firmware",
                "Upload failed.\n\n" + (out.strip() or "No output"),
            )
        return

    status_cb(f"Firmware flashed to {port}. Reconnect to use.")
    if HAS_QT and QMessageBox is not None:
        QMessageBox.information(
            parent,
            "Flash firmware",
            f"Firmware uploaded to {port}. Disconnect and reconnect the MC to use the new firmware.",
        )
