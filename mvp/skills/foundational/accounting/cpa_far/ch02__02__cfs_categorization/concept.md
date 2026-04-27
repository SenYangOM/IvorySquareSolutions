# Cash Flow Statement Categorization

## Core Idea

Every cash inflow and outflow on the Statement of Cash Flows (SCF) must be sorted into exactly one of three mutually exclusive buckets: **operating**, **investing**, or **financing**. The classification is not a matter of judgment in most cases—GAAP provides deterministic rules that map each transaction type to a single category. Getting the bucket wrong produces a misclassified SCF even if total net cash change is correct.

---

## The Three Buckets

| Category | Guiding Question | Typical Items |
|---|---|---|
| **Operating** | Does it relate to the entity's primary revenue-generating activities or working capital? | Cash from customers, cash to suppliers, interest paid (indirect method), taxes paid |
| **Investing** | Does it involve acquiring or disposing of long-term assets or investments? | Purchase/sale of PP&E, purchase/sale of securities (non-trading), loans made to others |
| **Financing** | Does it involve raising or repaying capital from owners or creditors? | Issuing stock, paying dividends, borrowing/repaying debt principal |

---

## Worked Example

A company performs four transactions in one period:

```
Transaction                          Amount     Category
─────────────────────────────────────────────────────────
Collected cash from customers       +$80,000    Operating
Purchased new delivery truck        -$25,000    Investing
Borrowed from bank (new loan)       +$40,000    Financing
Repaid principal on old loan        -$15,000    Financing
─────────────────────────────────────────────────────────
Net Operating Cash Flow             +$80,000
Net Investing Cash Flow             -$25,000
Net Financing Cash Flow             +$25,000
─────────────────────────────────────────────────────────
Total Net Change in Cash            +$80,000
```

Notice that the truck purchase is **investing**, not operating, even though the truck is used in daily operations. The asset's long-term nature drives the classification.

---

## Why Deterministic Reference Matters

Because classification rules are closed-form—each transaction maps to one and only one category under ASC 230—candidates and practitioners can build a reliable lookup framework. There is no estimation or probability involved; the answer is either correct or incorrect. A deterministic reference prevents the common error of letting economic intuition override the codified rule (e.g., placing interest paid in financing rather than operating under U.S. GAAP).

---

## Prereqs

- **Basic financial statement structure** — understanding that the SCF is a distinct primary statement alongside the income statement and balance sheet
- **Accrual vs. cash basis accounting** — recognizing why non-cash items must be excluded or adjusted
- **Direct vs. indirect method** — awareness that operating section presentation differs by method, though categorization rules remain the same
- **Working capital components** — ability to identify current assets and current liabilities that feed operating cash flows
