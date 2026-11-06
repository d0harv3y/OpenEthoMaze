#!/usr/bin/env python3
"""Read HTU21D temperature / relative humidity over Linux I2C (stdlib only).

Default: bus 1, addr 0x40 (common breakout wiring on Pi).
Env:
  HTU21D_BUS, HTU21D_ADDR
  HTU21D_AVG_N     — ring length (default 10) → 10 s window at 1 Hz sample
  HTU21D_BURST     — median-of-N per sample tick (default 1 at 1 Hz)
  HTU21D_RING      — ring path (default /run/bhvr/htu_ring.json)
  HTU21D_SOFT_RESET — force soft-reset every tick (default: only when ring empty)

Architecture:
  * ``sample`` tick (systemd timer @ 1 Hz) → push one conversion into the ring
  * announce (10 s) → read window min/max/mean; MQTT publishes means for the tile
    and full stats for REC JSONL
"""

from __future__ import annotations

import ctypes
import fcntl
import json
import os
import sys
import time
from pathlib import Path

I2C_SLAVE = 0x0703
I2C_RDWR = 0x0707
I2C_M_RD = 0x0001
CMD_TEMP_HOLD = 0xE3
CMD_HUM_HOLD = 0xE5
CMD_SOFT_RESET = 0xFE

# Datasheet RH temperature coefficient (%RH / °C).
_TEMP_COEFF = -0.15

# CRC-8 polynomial 0x131 (x^8 + x^5 + x^4 + 1), init 0 — HTU21D datasheet.
_POLY = 0x13100

_DEFAULT_RING = "/run/bhvr/htu_ring.json"
_DEFAULT_AVG_N = 10
# 1 Hz ticks: single conversion is enough; set HTU21D_BURST=3 for glitch reject.
_DEFAULT_BURST = 1


class _I2CMsg(ctypes.Structure):
    _fields_ = [
        ("addr", ctypes.c_uint16),
        ("flags", ctypes.c_uint16),
        ("len", ctypes.c_uint16),
        ("buf", ctypes.POINTER(ctypes.c_uint8)),
    ]


class _I2CRdwrIoctlData(ctypes.Structure):
    _fields_ = [
        ("msgs", ctypes.POINTER(_I2CMsg)),
        ("nmsgs", ctypes.c_uint32),
    ]


def _crc8(data: bytes) -> int:
    rem = 0
    for byte in data:
        rem ^= byte << 8
        for _ in range(8):
            if rem & 0x8000:
                rem = (rem << 1) ^ _POLY
            else:
                rem <<= 1
            rem &= 0xFFFF
    return (rem >> 8) & 0xFF


def _xfer_hold(fd: int, addr: int, cmd: int) -> bytes:
    """Hold-master: write cmd + read 3 bytes in one I2C_RDWR (repeated start)."""
    wbuf = (ctypes.c_uint8 * 1)(cmd)
    rbuf = (ctypes.c_uint8 * 3)()
    msgs = (_I2CMsg * 2)(
        _I2CMsg(addr, 0, 1, wbuf),
        _I2CMsg(addr, I2C_M_RD, 3, rbuf),
    )
    data = _I2CRdwrIoctlData(msgs, 2)
    last: OSError | None = None
    for _ in range(2):
        try:
            fcntl.ioctl(fd, I2C_RDWR, data)
            return bytes(rbuf)
        except OSError as exc:
            last = exc
            time.sleep(0.02)
    assert last is not None
    raise last


def _parse_raw(raw: bytes, *, expect_hum: bool) -> int:
    if len(raw) != 3:
        raise OSError(f"short read {len(raw)}")
    if _crc8(raw[:2]) != raw[2]:
        raise OSError(f"CRC fail data={raw!r}")
    val = ((raw[0] << 8) | raw[1]) & 0xFFFC
    if val == 0:
        raise OSError(f"zero sample data={raw!r}")
    is_hum_frame = bool(raw[1] & 0x02)
    if expect_hum != is_hum_frame:
        raise OSError(f"status mismatch expect_hum={expect_hum} data={raw!r}")
    return val


def _read_temp_fallback(fd: int) -> int:
    """write/stop/read path — works on Pi when I2C_RDWR stretch is flaky."""
    os.write(fd, bytes([CMD_TEMP_HOLD]))
    time.sleep(0.06)
    raw = os.read(fd, 3)
    return _parse_raw(raw, expect_hum=False)


def _bus_addr(
    bus: int | None,
    addr: int | None,
) -> tuple[int, int] | None:
    try:
        bus_env = os.environ.get("HTU21D_BUS")
        bus_i = int(bus_env) if bus_env is not None else (bus if bus is not None else 1)
        addr_env = os.environ.get("HTU21D_ADDR")
        if addr_env is not None:
            addr_i = int(addr_env, 0)
        else:
            addr_i = addr if addr is not None else 0x40
    except ValueError:
        return None
    return bus_i, addr_i


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _median(vals: list[float]) -> float:
    xs = sorted(vals)
    return xs[len(xs) // 2]


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals)


def _minmax_mean(vals: list[float]) -> dict[str, float]:
    return {
        "min": round(min(vals), 1),
        "max": round(max(vals), 1),
        "mean": round(_mean(vals), 1),
    }


def read_htu21d(
    *,
    bus: int | None = None,
    addr: int | None = None,
    soft_reset: bool | None = None,
) -> dict[str, float] | None:
    """Single conversion. Return ``{temp_c, rh_pct?}`` or ``None``."""
    parsed = _bus_addr(bus, addr)
    if parsed is None:
        return None
    bus_i, addr_i = parsed
    path = f"/dev/i2c-{bus_i}"
    if not os.path.exists(path):
        return None
    if soft_reset is None:
        soft_reset = os.environ.get("HTU21D_SOFT_RESET", "").strip() in (
            "1",
            "true",
            "yes",
        )
    fd = -1
    try:
        fd = os.open(path, os.O_RDWR)
        fcntl.ioctl(fd, I2C_SLAVE, addr_i)
        if soft_reset:
            try:
                os.write(fd, bytes([CMD_SOFT_RESET]))
                time.sleep(0.02)
            except OSError:
                pass

        try:
            t_raw = _parse_raw(_xfer_hold(fd, addr_i, CMD_TEMP_HOLD), expect_hum=False)
        except OSError:
            t_raw = _read_temp_fallback(fd)
        temp_c = -46.85 + 175.72 * (t_raw / 65536.0)
        out: dict[str, float] = {"temp_c": round(temp_c, 1)}

        try:
            h_raw = _parse_raw(_xfer_hold(fd, addr_i, CMD_HUM_HOLD), expect_hum=True)
            rh_lin = -6.0 + 125.0 * (h_raw / 65536.0)
            rh_pct = rh_lin + (25.0 - temp_c) * _TEMP_COEFF
            out["rh_pct"] = round(max(0.0, min(100.0, rh_pct)), 1)
        except OSError:
            pass
        return out
    except OSError:
        return None
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass


def _ring_path() -> Path:
    return Path(os.environ.get("HTU21D_RING") or _DEFAULT_RING)


def _load_ring(path: Path) -> list[dict[str, float]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, float]] = []
    for row in data:
        if not isinstance(row, dict) or "temp_c" not in row:
            continue
        try:
            item: dict[str, float] = {"temp_c": float(row["temp_c"])}
            if "rh_pct" in row and row["rh_pct"] is not None:
                item["rh_pct"] = float(row["rh_pct"])
            out.append(item)
        except (TypeError, ValueError):
            continue
    return out


def _save_ring(path: Path, ring: list[dict[str, float]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(ring), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _burst_sample(*, soft_reset: bool) -> dict[str, float] | None:
    """Median-of-N rapid conversions (I2C glitch reject), one logical sample."""
    n = _env_int("HTU21D_BURST", _DEFAULT_BURST)
    temps: list[float] = []
    rhs: list[float] = []
    for i in range(n):
        sample = read_htu21d(soft_reset=(soft_reset and i == 0))
        if sample is None:
            continue
        temps.append(float(sample["temp_c"]))
        if "rh_pct" in sample:
            rhs.append(float(sample["rh_pct"]))
        if i + 1 < n:
            time.sleep(0.05)
    if not temps:
        return None
    out: dict[str, float] = {"temp_c": round(_median(temps), 1)}
    if rhs:
        out["rh_pct"] = round(_median(rhs), 1)
    return out


def sample_htu21d_tick() -> dict[str, float] | None:
    """1 Hz path: take one sample and push into the ring. Return the raw tick."""
    ring_path = _ring_path()
    avg_n = _env_int("HTU21D_AVG_N", _DEFAULT_AVG_N)
    ring = _load_ring(ring_path)
    force_reset = os.environ.get("HTU21D_SOFT_RESET", "").strip() in (
        "1",
        "true",
        "yes",
    )
    sample = _burst_sample(soft_reset=(force_reset or not ring))
    if sample is None:
        return None
    ring.append(sample)
    ring = ring[-avg_n:]
    _save_ring(ring_path, ring)
    return sample


def window_stats() -> dict | None:
    """Read ring only (no new sample). Return means + min/max for announce/REC.

    Shape::
        {
          "temp_c": mean, "rh_pct": mean?,
          "n": int,
          "env": {
            "n": int,
            "temp_c": {"min", "max", "mean"},
            "rh_pct": {"min", "max", "mean"}?,  # omitted if no RH in window
          },
        }
    """
    ring = _load_ring(_ring_path())
    if not ring:
        return None
    temps = [float(r["temp_c"]) for r in ring]
    t_stats = _minmax_mean(temps)
    env: dict = {"n": len(ring), "temp_c": t_stats}
    out: dict = {
        "temp_c": t_stats["mean"],
        "n": len(ring),
        "env": env,
    }
    rhs = [float(r["rh_pct"]) for r in ring if "rh_pct" in r]
    if rhs:
        r_stats = _minmax_mean(rhs)
        env["rh_pct"] = r_stats
        out["rh_pct"] = r_stats["mean"]
    return out


def read_htu21d_smoothed(
    *,
    bus: int | None = None,
    addr: int | None = None,
) -> dict | None:
    """Announce path: window stats only (sampler timer owns 1 Hz ticks)."""
    del bus, addr
    return window_stats()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    mode = (args[0] if args else "").strip().lower()
    if mode in ("sample", "tick"):
        sample = sample_htu21d_tick()
        if sample is None:
            print("htu21d: unavailable", file=sys.stderr)
            return 1
        if "rh_pct" in sample:
            print(f"tick temp_c={sample['temp_c']} rh_pct={sample['rh_pct']}")
        else:
            print(f"tick temp_c={sample['temp_c']} rh_pct=NA")
        return 0
    if os.environ.get("HTU21D_RAW", "").strip() in ("1", "true", "yes") or mode == "raw":
        sample = read_htu21d(soft_reset=True)
        if sample is None:
            print("htu21d: unavailable", file=sys.stderr)
            return 1
        if "rh_pct" in sample:
            print(f"temp_c={sample['temp_c']} rh_pct={sample['rh_pct']}")
        else:
            print(f"temp_c={sample['temp_c']} rh_pct=NA")
        return 0
    stats = window_stats()
    if stats is None:
        # Warm-start: one tick then stats (CLI convenience when sampler not running).
        if sample_htu21d_tick() is None:
            print("htu21d: unavailable", file=sys.stderr)
            return 1
        stats = window_stats()
    if stats is None:
        print("htu21d: unavailable", file=sys.stderr)
        return 1
    if "rh_pct" in stats:
        print(
            f"temp_c={stats['temp_c']} rh_pct={stats['rh_pct']} "
            f"n={stats['n']} env={json.dumps(stats['env'], separators=(',', ':'))}"
        )
    else:
        print(
            f"temp_c={stats['temp_c']} rh_pct=NA "
            f"n={stats['n']} env={json.dumps(stats['env'], separators=(',', ':'))}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
