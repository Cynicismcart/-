# -*- coding: utf-8 -*-
from __future__ import annotations
from .models import PIDConfig
from .calcs import clamp

class PID:
    def __init__(self, cfg: PIDConfig):
        self.Kp, self.Ki, self.Kd = cfg.Kp, cfg.Ki, cfg.Kd
        self.integral_cap = cfg.integral_cap
        self.integral = 0.0
        self.prev_err = None
    def step(self, err: float) -> float:
        self.integral += err
        self.integral = clamp(self.integral, -self.integral_cap, self.integral_cap)
        deriv = 0.0 if self.prev_err is None else (err - self.prev_err)
        self.prev_err = err
        return float(self.Kp*err + self.Ki*self.integral + self.Kd*deriv)
