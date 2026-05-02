import math


def pmf(k: int, mu: float) -> float:
    if k < 0:
        return 0.0
    mu = max(float(mu), 0.0001)
    return math.exp(k * math.log(mu) - mu - math.lgamma(k + 1))


def cdf(k: float, mu: float) -> float:
    upper = math.floor(k)
    if upper < 0:
        return 0.0
    return sum(pmf(i, mu) for i in range(upper + 1))


def sf(k: float, mu: float) -> float:
    return max(0.0, 1.0 - cdf(k, mu))
