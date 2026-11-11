"""Regression tests for the loopholes closed in v2: observational data, fair holdout, fresh-data verdicts,
cleaning-path penalty, Data Scout disclosure and run limits."""
import os

os.environ["SKEPTIC_OFFLINE"] = "1"

import numpy as np
import pandas as pd
import pytest

from skeptic.backend import cleaner as CL
from skeptic.backend.adapters import tabular as TB
from skeptic.backend.adapters.claims_data import health_supplement
from skeptic.backend.court import judge as J, null_worlds as NW, stats as S
from skeptic.backend.court.pipeline import Court
from skeptic.backend.ledger import Ledger
from skeptic.backend.runner import run_scenario


# ------------------------------------------------------------------------------ #1 observational data / confounders
def test_detects_the_hidden_confounder():
    df = health_supplement(1, 4000).df
    found = TB.detect_confounders(df, "supplement", "health_score", exclude=("enrolled",))
    assert found and found[0]["column"] == "age_band"
    assert found[0]["assoc_treat"] > 0.1 and found[0]["assoc_outcome"] > 0.1


def test_independent_columns_are_not_confounders():
    rng = np.random.default_rng(0)
    n = 3000
    df = pd.DataFrame({"t": rng.integers(0, 2, n), "y": rng.normal(size=n), "noise": rng.choice(list("abc"), n)})
    assert TB.detect_confounders(df, "t", "y") == []


def test_upload_without_named_confounders_still_catches_simpson():
    """Before v2 an uploaded observational CSV with no confounders named was treated as randomised, and the
    pooled (reversed) effect could be called a DISCOVERY."""
    csv = health_supplement(1, 4000).df.drop(columns=["enrolled"]).to_csv(index=False)
    ev = []
    run_scenario("upload", {"csv": csv, "treat": "supplement", "outcome": "health_score", "n_worlds": 100}, ev.append, 0)
    assert not [e for e in ev if e["type"] == "error"]
    v = {e["hypothesis_id"]: e for e in ev if e["type"] == "verdict"}
    overall = v["health_score|overall"]
    assert overall["verdict"] == "LUCK" and "Simpson" in overall["cause_of_death"]
    assert all(x["design"] == "observational" for x in v.values())
    meta = next(e for e in ev if e["type"] == "meta")
    assert meta["panel"]["design"] == "observational" and meta["panel"]["confounders"][0]["column"] == "age_band"


def test_observational_without_confounders_is_flagged_not_passed():
    rng = np.random.default_rng(1)
    n = 2000
    df = pd.DataFrame({"t": rng.integers(0, 2, n), "seg": rng.choice(list("ab"), n)})
    df["y"] = 0.3 * df["t"] + rng.normal(size=n)
    s = TB.build_tabular_search(TB.TabularSpec(df=df, treat="t", outcomes=["y"], subgroup_cols=["seg"], observational=True), 0)
    simpson = next(f for f in s.attack_fns if f.__name__ == "simpson")
    r = simpson(s, 0, None)
    assert r["survived"] is False and r["severity"] == "medium"          # a caution flag, never a silent pass
    s2 = TB.build_tabular_search(TB.TabularSpec(df=df, treat="t", outcomes=["y"], subgroup_cols=["seg"], observational=False), 0)
    r2 = next(f for f in s2.attack_fns if f.__name__ == "simpson")(s2, 0, None)
    assert r2["survived"] is True


# ------------------------------------------------------------------------------ #4 fair holdout
def test_holdout_is_a_fair_sample_of_a_sorted_file():
    rng = np.random.default_rng(2)
    df = pd.DataFrame({"t": rng.integers(0, 2, 4000), "y": rng.normal(size=4000)}).sort_values("y").reset_index(drop=True)
    spec = TB.TabularSpec(df=df, treat="t", outcomes=["y"], subgroup_cols=[])
    S_df, H_df = TB._split(df, spec, 0)
    assert len(S_df) + len(H_df) == 4000
    assert abs(S_df["y"].mean() - H_df["y"].mean()) < 0.15      # the old 'last 25% of rows' split would differ by ~1.7 SD


def test_group_split_never_straddles():
    rng = np.random.default_rng(3)
    df = pd.DataFrame({"pid": np.repeat(np.arange(400), 5), "t": rng.integers(0, 2, 2000), "y": rng.normal(size=2000)})
    spec = TB.TabularSpec(df=df, treat="t", outcomes=["y"], subgroup_cols=[], group_col="pid")
    S_df, H_df = TB._split(df, spec, 0)
    assert not set(S_df["pid"]) & set(H_df["pid"])
    assert 0.15 < len(H_df) / 2000 < 0.35


# ------------------------------------------------------------------------------ #5 fresh data can change the verdict
def _verdict():
    return J.Verdict(hypothesis_id="h1", verdict=J.DISCOVERY, confidence=0.9, p_adj=0.01, p_luck_rate=0.01, level=0.03,
                     cause_of_death=None, confession="", search_size=10, cleaning_choices=0, n_null_worlds=100)


class _S:
    hyps = [{"id": "h1", "description": "d", "spec": {}}]
    unit = "days"


def test_reversal_on_fresh_data_downgrades():
    L = Ledger(); run = L.start_run("t")
    ev = []
    c = Court(L, emit=ev.append)
    v = _verdict()
    c._apply_fresh_data(_S(), run, v, {"n_days": 252, "t": -1.3, "confirmed": False}, 0)
    assert v.verdict == J.CANT_TELL and v.fresh_data == "reversed" and v.note
    assert ev[-1]["type"] == "verdict" and ev[-1]["verdict"] == J.CANT_TELL and ev[-1]["revised"] is True


def test_same_direction_on_fresh_data_keeps_discovery():
    L = Ledger(); run = L.start_run("t")
    c = Court(L, emit=lambda e: None)
    v = _verdict()
    c._apply_fresh_data(_S(), run, v, {"n_days": 252, "t": 0.8, "confirmed": False}, 0)
    assert v.verdict == J.DISCOVERY and v.fresh_data == "not yet confirmed"
    v2 = _verdict()
    c._apply_fresh_data(_S(), run, v2, {"n_days": 252, "t": 2.5, "confirmed": True}, 0)
    assert v2.fresh_data == "confirmed"


# ------------------------------------------------------------------------------ #2 cleaning paths are paid for
def test_alternative_paths():
    assert len(CL.all_paths()) == 8
    alts = CL.alternative_paths(CL.DEFAULT)
    assert len(alts) == 7 and CL.DEFAULT not in alts


def test_more_cleaning_paths_never_make_a_finding_look_better():
    rng = np.random.default_rng(4)
    T = 800
    pnl = rng.normal(0, 0.01, (20, T))
    pnl[0] += 0.0015                                   # one real-ish signal
    fac = rng.normal(0, 0.01, (T, 2))
    base = NW.run_null_worlds(pnl, fac, S.raw_t, "stationary_bootstrap", 200, seed=7)
    forks = pnl + rng.normal(0, 0.004, pnl.shape)      # the same ideas under other cleaning: correlated, not identical
    stacked, n_extra = NW.stack_forks(pnl, np.arange(20), forks, np.arange(20))
    assert n_extra == 20 and stacked.shape == (40, T)
    wide = NW.head(NW.run_null_worlds(stacked, fac, S.raw_t, "stationary_bootstrap", 200, seed=7), 20)
    assert wide.observed.shape == (20,)
    assert np.all(wide.p_single >= base.p_single - 1e-12)       # luck gets more tries, never fewer
    assert np.all(wide.null_max >= base.null_max - 1e-12)


# ------------------------------------------------------------------------------ #8 run limit
def test_busy_server_refuses_extra_runs():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from skeptic.backend import app as A
    held = 0
    while A._ACTIVE.acquire(blocking=False):
        held += 1
    try:
        r = TestClient(A.app).post("/api/run", json={"scenario": "health"})
        assert r.status_code == 429
    finally:
        for _ in range(held):
            A._ACTIVE.release()
