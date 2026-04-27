# Net present value (NPV)

Net present value (NPV) discounts a project's incremental cash flows
back to time zero at the required rate of return. Positive NPV signals
value creation; zero NPV is a break-even at the cost of capital;
negative NPV destroys value.

## Formula

For a project with cash flows `CF_0, CF_1, ..., CF_T` and discount rate
`r`:

    NPV = sum_{t=0}^{T} CF_t / (1 + r)^t

Sign convention: outflows are negative, inflows are positive. The
convention treats `CF_0` as the up-front investment (typically negative)
plus any time-zero cash inflow.

## Decision rule

- Accept if `NPV > 0`.
- Reject if `NPV < 0`.
- Indifferent if `NPV = 0`.

When projects are mutually exclusive, pick the one with the highest NPV.

## Worked example

Initial outlay 100, then four annual inflows of 30 each, at r = 8%:

    NPV = -100 + 30/1.08 + 30/1.08^2 + 30/1.08^3 + 30/1.08^4
        = -100 + 27.778 + 25.720 + 23.815 + 22.051
        =  -0.636

The project is essentially break-even at 8%; raising r above ~7.7%
flips the sign.

## Sensitivity intuition

NPV is monotonically decreasing in `r` for ordinary cash-flow patterns
(one outflow followed by inflows). Break-even `r*` solving `NPV(r*) = 0`
is the internal rate of return — see the IRR subsection for pitfalls.

## Why code-backed

NPV is a textbook closed-form computation. An LLM can recite the
formula correctly but routinely off-by-arithmetics on cases with
4+ periods or nontrivial discount rates. The code reference in
`code/npv.py` makes the computation deterministic.
