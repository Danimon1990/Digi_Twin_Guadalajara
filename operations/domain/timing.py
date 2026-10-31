"""Validated, seedable timing inputs. Distribution shapes are modeling assumptions."""
from __future__ import annotations
import math
import random


def validate_duration(spec: object) -> None:
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        if not math.isfinite(spec) or spec < 0:
            raise ValueError('duration must be finite and nonnegative')
        return
    if not isinstance(spec, dict) or spec.get('distribution') not in {'uniform', 'triangular'}:
        raise ValueError('duration requires a number, uniform or triangular distribution')
    lo, hi = spec.get('min_s'), spec.get('max_s')
    validate_duration(lo)
    validate_duration(hi)
    if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)) or hi < lo:
        raise ValueError('duration bounds must be numeric and ordered')
    if spec['distribution'] == 'triangular':
        mode = spec.get('mode_s')
        validate_duration(mode)
        if not isinstance(mode, (int, float)) or not lo <= mode <= hi:
            raise ValueError('triangular mode must lie inside bounds')


def sample_duration(spec: object, rng: random.Random) -> float:
    validate_duration(spec)
    if isinstance(spec, (int, float)):
        return float(spec)
    if spec['distribution'] == 'uniform':
        return rng.uniform(spec['min_s'], spec['max_s'])
    return rng.triangular(spec['min_s'], spec['max_s'], spec['mode_s'])


def sample_portions(spec: object, quantity: float, rng: random.Random) -> float:
    """Independent draws per whole portion; fractional remainder scales one draw."""
    if not math.isfinite(quantity) or quantity <= 0:
        raise ValueError('quantity must be finite and positive')
    count = int(quantity)
    remainder = quantity - count
    return sum(sample_duration(spec, rng) for _ in range(count)) + (
        sample_duration(spec, rng) * remainder if remainder else 0.0
    )
