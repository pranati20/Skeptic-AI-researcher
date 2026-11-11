# Skeptic: an AI researcher that checks its own luck

> *Finding patterns in data is easy. Knowing which ones to trust is hard.*

Give an AI a dataset and ask it to find something interesting, and it will. Try 100 ideas and about 5 will look "statistically significant" by pure chance. An AI agent can try thousands of ideas in a minute, so it can produce convincing fake discoveries faster than any human ever could.

**Skeptic is an AI researcher built to catch itself doing this.** A swarm of agents hunts for patterns. Then a "Court" tries hard to prove each pattern is just luck, and only the ones that survive are called discoveries.

It works on stock signals, sports betting, A/B tests, health claims, or any CSV you upload. You can also just type a question and it finds a public dataset to answer it.

---

## The problem with naive AI researchers

| What a naive AI researcher does | Why it goes wrong | What Skeptic does instead |
|---|---|---|
| Tries 141 trading ideas and reports the 59 with p < 0.05 | With that many tries, plenty of noise will clear p < 0.05 | Logs **every** idea in a ledger and tests the winner against the best result luck produced across the *whole* search |
| Reports only the winning idea | Hides how many ideas were tried, which is the main thing a reader needs to know | Gives a "confession" with every result: *"I tried 141 ideas to find this. Luck alone would do this well 0.3% of the time."* |
| Picks whichever cleaning step makes the result look best | Each data-cleaning choice is another hidden roll of the dice | Re-runs the search under **every** cleaning path, and luck gets to pick the best one too |
| "Supplement users are less healthy" (true in the raw data) | Older people take more supplements and are less healthy. Hold age fixed and the effect **reverses** (Simpson's paradox) | Detects confounders automatically, compares like with like, and labels non-experimental results "association, not cause" |
| A/B test: "variant B wins!" after checking the results 10 times | Peeking and stopping at the first good-looking moment inflates false wins | A peeking-aware test: an early win counts only if the final data still clears an adjusted bar |
| Backtest says +$217,598 | Built on lookahead, survivorship bias, ignored trading costs, or plain market beta | Skeptic checks for each of these, re-runs the idea to confirm, and shows what the money really would have been |
| "This betting strategy has +37% ROI" | Betting on a random side earns the same | A placebo test kills it |

Every claim ends with one of three honest verdicts: **DISCOVERY**, **LUCK**, or **CAN'T TELL YET** (with an estimate of how much more data would settle it).

---

## Does it actually work? (ground-truth benchmark)

Saying "trust me" isn't proof. So we built a simulated market where **we know the answer**. It has 500 candidate signals over 200 assets:

- **5** are real
- **10** are decoys that only look good because they track known market factors
- **5** are traps (lookahead or survivorship bias)
- the rest are noise, with realistic fat tails and volatility clustering

Every method is run on 20 random seeds:

<!--BENCH-->
| Method | Claimed discoveries | Actually real | False | False-discovery rate |
|---|---|---|---|---|
| Naive analyst (p < 0.05) | 50.3 | 5.0 | 45.3 | **90%** |
| Benjamini-Hochberg | 16.2 | 4.7 | 11.6 | 71% |
| Single train/test split | 13.5 | 4.3 | 9.2 | 69% |
| Bonferroni | 12.1 | 4.3 | 7.8 | 64% |
| Deflated Sharpe ratio | 5.2 | 2.5 | 2.7 | 52% |
| **Skeptic (full Court)** | **3.9** | **3.85** | **0.0** | **0%** |
<!--/BENCH-->

**The naive analyst is wrong 9 times out of 10. Skeptic made zero false discoveries in 20 runs and still found 77% of the real signals.**

Being honest about the limits:
- **0 observed false discoveries doesn't mean 0 risk.** Across ~80 claims, the 95% upper bound on the error rate is about 4%.
- **Safety costs power.** Weak real signals (Sharpe below ~2) are often called LUCK or CAN'T TELL YET. The benchmark measures exactly which check rejects real signals, so we know what to tune next.
- **It can't see what it isn't given.** If a confounder is missing from the data, a decoy can pass (measured: 5 of 10 decoys pass when two factors are hidden).

Re-run it yourself: `python -m skeptic.backend.benchmark.run_benchmark --seeds 20`

---

## How it works

```
 Question / dataset
        │
   Data Scout ── finds a public dataset if you only typed a question
        │
     Cleaner ── every cleaning choice is logged as a "forking path"
        │
 Researcher swarm ── 6 agent families propose ideas as structured JSON in a safe formula language (no eval)
        │
     LEDGER ── every idea ever tried, by every agent
        │
 Null worlds ── re-run the ENTIRE search 300× on data where nothing is real; record the best luck produced
        │
 Credibility budget ── online error control: the more the swarm guesses, the higher the bar gets
        │
   Skeptics ── adversarial checks: leakage · survivorship · costs · regimes · concentration · hidden beta · Simpson · peeking · placebo
        │
     Judge ── verdict + confidence + "how much more data" + a commitment hash
        │
 Fresh-data check ── scored on data the search never saw; a claim that reverses is downgraded
        │
 Plain-English answer ── written only from findings that survived
```

**Design principle: the statistics do the heavy lifting, and LLMs do only what statistics can't.** The null worlds, ledger, multiple-testing math and backtests are plain numpy/scipy and cost zero tokens. LLMs propose ideas, review specs, read papers and write the explanation. Everything runs offline with a mock LLM. Claude is optional.

### The core idea, in one paragraph
Don't ask "does the winning idea look good?" Ask **"would luck alone, searching just as hard, have found something this good?"** Skeptic answers that directly. It builds many fake versions of the data where any real signal is destroyed but the messy structure (fat tails, volatility clusters, correlations) is kept. It runs the *exact same search* in each one and records the best result luck produced. A finding only counts if it beats that. This is White's Reality Check and Romano-Wolf max-statistic testing, applied to an AI agent's whole search loop.

---

## What makes it more than a stats script

- **Audits the search, not the result.** The ledger counts every idea, every agent and every cleaning choice. That count goes straight into the math, not just into a footnote.
- **Adversarial by design.** Skeptic agents actively try to kill each finding. Each dead idea goes to a "graveyard" with its cause of death, like *"died of beta (it was never alpha)"* or *"died after costs"*.
- **Knows the difference between correlation and causation.** Non-experimental data is adjusted for automatically detected confounders and labelled as an association.
- **Tests on data it never saw.** Each discovery is locked with a SHA-256 hash, then scored on a held-out slice. If it reverses there, it isn't a discovery.
- **Says "I don't know."** CAN'T TELL YET comes with a power estimate and how much more data would be needed.
- **Shows the cost of being fooled.** The "Cost of Illusion" chart puts the backtest's promise next to what the strategy really delivers.
- **Grounded in literature.** A Librarian agent pulls real papers (Crossref, arXiv, OpenAlex) and checks whether they actually apply to this data, e.g. whether the sample overlaps or the effect decayed after publication.
- **Honest guardrails everywhere.** No trading advice, simulated data is labelled, and the failure modes are measured and shown.

---

## Try it

The package imports itself as `skeptic`, so clone it into a folder with that name:

```bash
git clone https://github.com/pranati20/Skeptic-AI-researcher.git skeptic
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r skeptic/requirements.txt

python -m uvicorn skeptic.backend.app:app --port 8000   # open http://localhost:8000
python -m skeptic.demo                                   # 3-minute narrated story in the terminal
python -m pytest skeptic/tests -q                        # 105 tests, including known-answer statistics
```

- No API key needed. To use real Claude, set `SKEPTIC_USE_LLM=1` and `ANTHROPIC_API_KEY=...`.
- To turn off all network use, set `SKEPTIC_OFFLINE=1`.
- The UI is pre-built in `frontend/dist`. To work on it: `cd skeptic/frontend && npm install && npm run dev`.

### Example scenarios in the app
| Scenario | What it shows |
|---|---|
| Stock-picking AI (simulated) | The naive analyst claims 59 discoveries. Skeptic keeps 10, and all 10 are real |
| Real stocks 2010–2025 | 117 large caps. Nothing survives, and the app explains why (survivor-only universe) |
| Sports betting | +37% ROI, but a random side does just as well |
| A/B test | Peeking kills early "wins". One real segment effect is found |
| Health claim | Simpson's paradox: the raw effect reverses once age is held fixed |
| Your CSV / your question | The same Court on your own data, or on a public dataset found for your question |

---

## Tech stack
**Backend:** Python, FastAPI + WebSockets (live event stream), numpy/scipy/pandas/statsmodels, SQLite ledger, Anthropic SDK with prompt-hash disk caching and a live token/cost meter.
**Frontend:** React, TypeScript, Vite, Tailwind, framer-motion, Recharts.
**Testing:** pytest (known-answer statistical tests, DSL safety, every Skeptic check, end-to-end Court runs) plus a Playwright UI smoke test.

**Methods used:** White's Reality Check, Hansen's SPA, Romano-Wolf step-down, Deflated Sharpe Ratio, Benjamini-Hochberg, Foster-Stine alpha-investing, stationary bootstrap, IAAFT surrogates, stratified permutation tests. All are known methods. The contribution is wiring them into one system that audits an autonomous agent's own search, and measuring that it works.

---

## Repo layout
```
backend/
  app.py, runner.py        API + scenario orchestration (live event stream)
  court/                   null worlds, multiple testing, credibility budget, judge, power, pre-registration
  prosecutors/             the Skeptic checks
  hunters/, features_dsl.py  researcher agents + safe formula language
  adapters/                markets, real equities, betting, tabular (A/B, health, uploads)
  datascout.py, literature.py, conclude.py   find data, find papers, write the answer
  benchmark/               the ground-truth proof
frontend/                  React UI
tests/                     105 tests
```

*Skeptic reduces false discoveries and measures uncertainty. It doesn't prove anything is true, and nothing here is financial or medical advice.*
