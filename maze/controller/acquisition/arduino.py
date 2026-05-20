"""
Arduino serial protocol: send duty cycle (0-100) for vibration PWM.

Message format: D%d\\n (e.g. D50\\n for 50% duty). Enforce min/max (default 35-85%).
Identity: send ?\\n; firmware must respond with VAST_CONTROLLER_DUTY\\n.
"""

from __future__ import annotations

import time
from typing import List, Optional

try:
    import serial

    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False

# Expected response line (without newline) for identity query "?\n"
FIRMWARE_IDENTITY = "VAST_CONTROLLER_DUTY"


class ArduinoStimulus:
    """Send duty cycle to Arduino over serial. Turn off on disconnect/error."""

    def __init__(
        self,
        port: Optional[str] = None,
        baud: int = 9600,
        min_duty_pct: float = 35.0,
        max_duty_pct: float = 85.0,
    ):
        if not HAS_SERIAL:
            raise RuntimeError("pyserial is required for ArduinoStimulus")
        self.port = port
        self.baud = baud
        self.min_duty_pct = min_duty_pct
        self.max_duty_pct = max_duty_pct
        self._ser: Optional[serial.Serial] = None
        self._read_buffer: str = ""

    def connect(self, port: Optional[str] = None) -> bool:
        p = port or self.port
        if not p:
            return False
        try:
            self._ser = serial.Serial(p, self.baud, timeout=0.1)
            self._read_buffer = ""
            # Let the board finish reset after port open (DTR often triggers reset)
            time.sleep(1.8)
            if not self._check_firmware():
                self.disconnect()
                return False
            self.set_duty(0)
            return True
        except Exception:
            self._ser = None
            return False

    def _check_firmware(self, timeout_s: float = 1.5) -> bool:
        """Send identity query and verify firmware responds with VAST_CONTROLLER_DUTY."""
        if self._ser is None or not self._ser.is_open:
            return False
        try:
            self._ser.reset_input_buffer()
            # Send identity query up to 3 times in case the first is lost during startup
            for _ in range(3):
                self._ser.write(b"?\n")
                deadline = time.monotonic() + timeout_s
                line_buf = ""
                while time.monotonic() < deadline:
                    n = self._ser.in_waiting
                    if n > 0:
                        line_buf += self._ser.read(n).decode("ascii", errors="ignore")
                    while "\n" in line_buf or "\r" in line_buf:
                        sep = "\n" if "\n" in line_buf else "\r"
                        raw_line = line_buf.split(sep)[0]
                        line_buf = line_buf[line_buf.index(sep) + 1 :].lstrip("\r\n")
                        line = raw_line.strip().replace("\r", "")
                        if line and (line == FIRMWARE_IDENTITY or FIRMWARE_IDENTITY in line):
                            return True
                    time.sleep(0.02)
                time.sleep(0.15)
            return False
        except Exception:
            return False

    def disconnect(self) -> None:
        if self._ser is not None:
            try:
                self.set_duty(0)
            except Exception:
                pass
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        self._read_buffer = ""

    def set_duty(self, duty_pct: float) -> None:
        if self._ser is None or not self._ser.is_open:
            return
        # Allow a true "off" (0%) while clamping non-zero values to the configured min/max range.
        if duty_pct <= 0:
            d = 0
        else:
            d = max(self.min_duty_pct, min(self.max_duty_pct, duty_pct))
        d = int(round(d))
        try:
            self._ser.write(f"D{d}\n".encode("ascii"))
        except Exception:
            self.disconnect()

    def off(self) -> None:
        """Turn off stimulus."""
        self.set_duty(0)

    def read_pending_commands(self) -> List[str]:
        """Non-blocking read of incoming lines; returns list of single-char commands (e.g. ['T'] for start trial)."""
        out: List[str] = []
        if self._ser is None or not self._ser.is_open:
            return out
        try:
            n = self._ser.in_waiting
            if n > 0:
                self._read_buffer += self._ser.read(n).decode("ascii", errors="ignore")
            while "\n" in self._read_buffer or "\r" in self._read_buffer:
                line, sep, rest = self._read_buffer.partition("\n")
                if not sep:
                    line, sep, rest = self._read_buffer.partition("\r")
                self._read_buffer = rest.lstrip("\r\n")
                cmd = line.strip()
                if cmd:
                    out.append(cmd[0] if cmd else "")
        except Exception:
            self.disconnect()
        return out

    @property
    def connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def __enter__(self) -> "ArduinoStimulus":
        if self.port:
            self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.disconnect()
