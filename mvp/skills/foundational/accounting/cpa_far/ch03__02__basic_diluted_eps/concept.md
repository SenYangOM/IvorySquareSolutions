# Basic vs. Diluted EPS

## Core Idea

Earnings per share (EPS) answers a simple question: how much of a company's net income belongs to each share of common stock? Two versions exist because the *current* share count and the *potential* share count can differ significantly.

**Basic EPS** uses only shares that are already outstanding — no hypotheticals.

**Diluted EPS** asks: *if every instrument that could become common stock actually did*, how much would each share earn? It is always ≤ Basic EPS (or equal, never higher).

---

## Formulas

```
Basic EPS
─────────────────────────────────────────────────────
         Net Income − Preferred Dividends
Basic = ─────────────────────────────────────────────
         Weighted-Average Common Shares Outstanding


Diluted EPS
─────────────────────────────────────────────────────
         Adjusted Net Income
Diluted = ──────────────────────────────────────────
           WACSO + Dilutive Potential Shares
```

**Adjusted Net Income** adds back after-tax interest on convertible debt (since conversion eliminates that interest expense).

**Dilutive Potential Shares** includes:
- Stock options and warrants (treasury-stock method)
- Convertible preferred stock (if-converted method)
- Convertible bonds (if-converted method)

---

## Worked Example

```
Given:
  Net income              = $500,000
  Preferred dividends     = $20,000
  WACSO                   = 100,000 shares
  Stock options (dilutive) → 5,000 incremental shares (treasury-stock method)

Basic EPS:
  ($500,000 − $20,000) / 100,000 = $4.80

Diluted EPS:
  $480,000 / (100,000 + 5,000) = $4.57
```

The $0.23 drop illustrates dilution — existing shareholders' slice shrinks when potential shares enter the denominator.

---

## Anti-Dilution Rule

An instrument is **anti-dilutive** if including it would *increase* EPS. Anti-dilutive securities are excluded from the diluted calculation entirely. This prevents companies from artificially inflating diluted EPS.

---

## Why Closed-Form Determinism Matters

Both EPS figures follow exact arithmetic paths defined by GAAP (ASC 260). Given the same inputs — income, dividends, share counts, conversion terms — every preparer must arrive at the identical number. There is no estimation or judgment in the arithmetic itself (though judgment enters when classifying instruments as dilutive vs. anti-dilutive). This determinism makes EPS a reliable, auditable benchmark and a safe target for exam questions with a single correct numerical answer.

---

## Prereqs

- **Weighted-average shares outstanding** — understanding how share counts are time-weighted across a period
- **Preferred dividends** — distinguishing cumulative vs. non-cumulative treatment in the numerator
- **Treasury-stock method** — computing incremental shares from options and warrants
- **If-converted method** — adjusting both numerator and denominator for convertible securities
- **Net income and income statement structure** — identifying the correct earnings figure before EPS calculation
