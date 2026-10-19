import numpy as np

# Every distribution is parametrised by mean and standard deviation,
# so experiments with different distributions stay comparable.
# Keys are internal identifiers, values are labels shown in the GUI.
DISTRIBUTIONS = {
    "normal": "normalny",
    "uniform": "jednostajny",
    "exponential": "wykładniczy (przesunięty)",
    "gamma": "gamma",
    "lognormal": "log-normalny",
    "poisson": "Poissona (odchylenie ignorowane)",
}


def _sample(rng, distribution, mean, std, n):
    if distribution == "normal":
        return rng.normal(mean, std, n)
    if distribution == "uniform":
        # U(a, b) has std = (b - a) / sqrt(12)
        half_width = np.sqrt(3) * std
        return rng.uniform(mean - half_width, mean + half_width, n)
    if distribution == "exponential":
        # Shifted exponential: mean = shift + scale, std = scale
        return mean - std + rng.exponential(std, n)
    if distribution == "gamma":
        if mean <= 0:
            raise ValueError("Rozkład gamma wymaga średniej > 0")
        shape = (mean / std) ** 2
        scale = std ** 2 / mean
        return rng.gamma(shape, scale, n)
    if distribution == "lognormal":
        if mean <= 0:
            raise ValueError("Rozkład log-normalny wymaga średniej > 0")
        sigma2 = np.log(1 + (std / mean) ** 2)
        mu = np.log(mean) - sigma2 / 2
        return rng.lognormal(mu, np.sqrt(sigma2), n)
    if distribution == "poisson":
        # Poisson has std = sqrt(mean), so the given std is ignored
        if mean < 0:
            raise ValueError("Rozkład Poissona wymaga średniej >= 0")
        return rng.poisson(mean, n).astype(float)
    raise ValueError(f"Nieznany rozkład: {distribution}")


def generate_points(distribution, means, stds, n_alternatives, n_criteria,
                    seed=None, round_values=False):
    """Return a list of tuples (alternatives), each of length n_criteria.

    means / stds: a single number (shared by all criteria)
    or a list with a separate value for each criterion.
    """
    if n_alternatives < 1 or n_criteria < 1:
        raise ValueError("Liczba alternatyw i kryteriów musi być >= 1")
    means = _expand(means, n_criteria, "średnich")
    stds = _expand(stds, n_criteria, "odchyleń")
    if distribution != "poisson" and any(s <= 0 for s in stds):
        raise ValueError("Odchylenie standardowe musi być > 0")

    rng = np.random.default_rng(seed)
    columns = [_sample(rng, distribution, m, s, n_alternatives) for m, s in zip(means, stds)]
    data = np.column_stack(columns)
    if round_values:
        data = np.round(data)
    return [tuple(float(v) for v in row) for row in data]


def _expand(values, k, name):
    if np.isscalar(values):
        return [float(values)] * k
    values = [float(v) for v in values]
    if len(values) == 1:
        return values * k
    if len(values) != k:
        raise ValueError(f"Liczba {name} ({len(values)}) nie zgadza się z liczbą kryteriów ({k})")
    return values
