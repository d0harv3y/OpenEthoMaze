"""Stage III bout AR-HMM configuration (ADR 0007)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from maze.kpms.fit import FitConfig


@dataclass(frozen=True)
class BoutArhmmConfig:
    num_states: int = 20
    nlags: int = 2
    kappa: float = 50.0
    alpha: float = FitConfig.alpha
    gamma: float = FitConfig.gamma
    S_0_scale: float = 0.01
    K_0_scale: float = 10.0
    num_iters: int = 200
    seed: int = 42

    def trans_hypparams(self) -> dict[str, float | int]:
        return {
            "num_states": int(self.num_states),
            "kappa": float(self.kappa),
            "alpha": float(self.alpha),
            "gamma": float(self.gamma),
        }

    def ar_hypparams(self, latent_dim: int) -> dict[str, float | int]:
        return {
            "latent_dim": int(latent_dim),
            "nlags": int(self.nlags),
            "S_0_scale": float(self.S_0_scale),
            "K_0_scale": float(self.K_0_scale),
        }

    def to_json_dict(self) -> dict[str, float | int]:
        return asdict(self)
