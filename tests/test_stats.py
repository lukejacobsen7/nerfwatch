from nerfwatch.stats import cusum, mean_ci, rasch_theta


def test_cusum_fires_on_sustained_drop_not_noise():
    stable = [0.80, 0.82, 0.78, 0.81, 0.79, 0.80, 0.79, 0.81, 0.80]
    assert cusum(stable, baseline_n=5, min_sd=0.05).alarm_idx is None
    dropped = stable[:5] + [0.60, 0.58, 0.61, 0.59]
    c = cusum(dropped, baseline_n=5, min_sd=0.05)
    assert c.alarmed and c.direction == "down"
    blip = stable[:5] + [0.55] + [0.80, 0.81, 0.79, 0.80]
    assert cusum(blip, baseline_n=5, min_sd=0.05).alarm_idx is None


def test_cusum_handles_missing_and_short():
    assert cusum([None, None], baseline_n=5) is None
    assert cusum([0.5], baseline_n=5) is None
    assert cusum([0.5, None, 0.6, 0.5, 0.6, 0.5], baseline_n=5) is not None


def test_rasch_monotone_and_finite():
    hi, _ = rasch_theta([(b, True) for b in (-2, -1, 0, 1, 2)])
    mid, _ = rasch_theta([(-2, True), (-1, True), (0, True), (1, False), (2, False)])
    lo, _ = rasch_theta([(b, False) for b in (-2, -1, 0, 1, 2)])
    assert hi > mid > lo
    assert all(abs(x) < 5 for x in (hi, mid, lo))


def test_bootstrap_ci_brackets_mean():
    m, lo, hi = mean_ci([1, 1, 1, 0, 1, 0, 1, 1, 1, 1])
    assert lo <= m <= hi and 0 <= lo and hi <= 1
