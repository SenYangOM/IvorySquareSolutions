# ASC 606 Five-Step Revenue Recognition Model

## Core Idea

ASC 606 establishes a single, principles-based framework that governs when and how much revenue a company records. Rather than relying on industry-specific rules, the standard channels every revenue transaction through five sequential steps. Completing all five steps tells you both the *timing* (when to recognize) and the *amount* (how much to recognize) of revenue.

## The Five Steps

```
Step 1 ──► Identify the CONTRACT with a customer
              ↓
Step 2 ──► Identify the PERFORMANCE OBLIGATIONS
           (distinct goods or services promised)
              ↓
Step 3 ──► Determine the TRANSACTION PRICE
           (variable consideration, constraints,
            significant financing components)
              ↓
Step 4 ──► ALLOCATE the transaction price
           to each performance obligation
           (using standalone selling prices)
              ↓
Step 5 ──► RECOGNIZE revenue when (or as)
           each performance obligation is SATISFIED
```

## Worked Example

A software company signs a $9,000 contract covering:
- A software license (standalone price: $6,000)
- One year of support (standalone price: $3,000)

**Step 1** – A valid contract exists (written agreement, collectability probable).  
**Step 2** – Two distinct performance obligations: license + support.  
**Step 3** – Transaction price = $9,000 (no variable consideration here).  
**Step 4** – Allocate proportionally:
```
License : $9,000 × (6,000 / 9,000) = $6,000
Support : $9,000 × (3,000 / 9,000) = $3,000
```
**Step 5** – License recognized at a *point in time* (delivery day); support recognized *over time* (ratably across 12 months → $250/month).

## Why a Deterministic Reference Matters

Because ASC 606 is closed-form and rule-sequenced, an AI model that paraphrases the steps from memory frequently collapses Steps 2 and 4, misplaces variable-consideration constraints, or conflates point-in-time with over-time recognition. A deterministic reference page pins the exact ordering and allocation mechanics so every downstream explanation, practice problem, and exam simulation draws from the same authoritative source—eliminating drift across a student's study session.

## Prereqs

- **Revenue recognition overview** – conceptual purpose of matching revenue to economic activity
- **Contract law basics** – enforceability, rights, and payment terms that qualify a contract under Step 1
- **Standalone selling price methods** – adjusted market assessment, expected cost plus margin, residual approach used in Step 4
- **Performance obligation criteria** – "distinct" good-or-service test (capable of being distinct + distinct within the contract)
- **Variable consideration and constraint** – expected value vs. most-likely-amount methods applied in Step 3
