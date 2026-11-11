# Skeptic

An AI researcher that checks whether its own discoveries are real or just luck.

## Why I built this

If you test enough ideas on a dataset, some of them will look good by accident. Test 100 random ideas and about 5 will pass the usual "p < 0.05" bar even if none of them mean anything.

People already fall into this trap. AI agents fall into it much faster, because they can try thousands of ideas in a minute and then confidently report the ones that happened to work. I wanted to build an agent that does the opposite: one that assumes every finding is luck until it can show otherwise.

This started as a hackathon project for the Brevan Howard challenge: *"Finding patterns in data is easy; knowing which ones to trust is hard."*

## What it does

You give it data (or just a question, and it goes and finds a public dataset). A group of AI agents comes up with ideas and tests them. Then a second stage, which I call the Court, tries to knock each idea down.

Every idea ends up with one of three answers:

- **Discovery**: it survived everything.
- **Luck**: it didn't.
- **Can't tell yet**: there isn't enough data, and it tells you roughly how much more you'd need.

## A few examples

**Stock signals.** The AI tries 141 trading ideas on simulated market data. A naive approach (keep anything with p < 0.05) reports 59 "discoveries". Skeptic keeps 10. Because the data is simulated, we know the truth, and all 10 of those are real.

**The supplement trap.** In one dataset, people who take supplements look less healthy than people who don't. But older people take more supplements and are also less healthy. Once you compare people of the same age, supplements actually help. Skeptic spots that age is mixed up with both, compares like with like, and gets the right answer. It does this even if you don't tell it to look at age.

**A/B test peeking.** Someone checks their experiment results 10 times and stops as soon as variant B looks like it's winning. That makes false wins much more likely. Skeptic accounts for the peeking, and most of those early wins don't survive.

**Sports betting.** A strategy shows +37% return. Skeptic tries betting on a random side instead and gets the same return, so the strategy wasn't doing anything.

**Real stocks, 2010 to 2025.** Nothing survives, and Skeptic explains why: the price data only includes companies that still exist today, which makes everything look better than it really was.

## How it decides

The main idea is simple. Don't ask "does the best idea look good?" Ask "if nothing real were going on, and I searched just as hard, how good would the best result look?"

To answer that, Skeptic makes a few hundred fake copies of the data where any real pattern has been scrambled away, but the messiness of real data (big jumps, calm and wild periods) is kept. It runs the exact same search on every copy and records the best result luck produced each time. A real finding has to beat that.

After that, each surviving idea gets attacked from different angles:

- Did it accidentally use information from the future?
- Does it disappear after trading costs?
- Did it only work in one lucky year?
- Is it just tracking the overall market?
- Does it only hold for companies that survived?
- Does the effect flip when you compare like with like?

Finally, it's tested on a slice of data the search never touched. If it goes the other way there, it doesn't count.

It also keeps a record of everything it tried, including small choices like how the data was cleaned. Each result comes with a line like: *"I tried 141 ideas to find this. Luck alone would do this well 0.3% of the time."*

## Does it work?

I built a test market where I know the right answers: 500 signals, of which 5 are real, 10 are fakes that just follow the market, 5 are traps, and the rest are noise. Then I ran each method 20 times.

<!--BENCH-->
| Method | Claimed | Actually real | Wrong |
|---|---|---|---|
| Naive (p < 0.05) | 50.3 | 5.0 | 45.3 |
| Benjamini-Hochberg | 16.2 | 4.7 | 11.6 |
| Train/test split | 13.5 | 4.3 | 9.2 |
| Bonferroni | 12.1 | 4.3 | 7.8 |
| Deflated Sharpe | 5.2 | 2.5 | 2.7 |
| Skeptic | 3.9 | 3.85 | 0.0 |
<!--/BENCH-->

The naive approach is wrong about 9 times out of 10. Skeptic didn't make a single false claim across the 20 runs, and it still found about 77% of the real signals.

It's not perfect, and I'd rather say so up front:

- **It's cautious.** Weak real effects often get labelled "luck" or "can't tell yet". That's the trade-off for not fooling itself.
- **Zero mistakes in 20 runs doesn't mean it never makes mistakes.** The honest upper bound is around 4%.
- **It can't adjust for things that aren't in the data.** When I hid two market factors from it, half of the fake signals got through.
- **The benchmark is my own simulation.** Real data is messier.

## Where the AI is (and isn't) used

The statistics don't use an LLM at all. The scrambled copies, the record of tries and the backtests are plain Python (numpy and scipy), so they're fast, cheap and repeatable. LLMs are used for the parts that need language: coming up with ideas, reviewing them for mistakes, reading research papers and writing the final answer in plain English.

Everything runs offline without an API key, using a stand-in model. Plugging in Claude is optional.

## Running it

The code expects to live in a folder called `skeptic`, so clone it like this:

```bash
git clone https://github.com/pranati20/Skeptic-AI-researcher.git skeptic
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r skeptic/requirements.txt

python -m uvicorn skeptic.backend.app:app --port 8000
```

Then open http://localhost:8000.

Other useful commands:

```bash
python -m skeptic.demo                                    # a short guided story in the terminal
python -m pytest skeptic/tests -q                         # run the tests
python -m skeptic.backend.benchmark.run_benchmark --seeds 20   # re-run the benchmark
```

To use real Claude, set `SKEPTIC_USE_LLM=1` and `ANTHROPIC_API_KEY`. To keep it fully offline, set `SKEPTIC_OFFLINE=1`.

## Built with

Python, FastAPI and WebSockets on the backend, with numpy, scipy, pandas and SQLite. React, TypeScript, Tailwind and Recharts on the frontend. Tests use pytest, plus a Playwright check of the UI.

The statistical methods are established ones: White's Reality Check, Romano-Wolf, Hansen's SPA, the Deflated Sharpe Ratio, Benjamini-Hochberg and alpha-investing. What I added is putting them together so they check an AI agent's entire search, and then measuring whether that actually works.

---

None of this is financial or medical advice. Skeptic is good at telling you when something is probably luck. It can't prove that something is true.
