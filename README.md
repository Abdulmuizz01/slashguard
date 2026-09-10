# SlashGuard: Web-Grounded Parametric Exploit Escrow

**Submission Track:** Builder — Intelligent Contracts  
**Author:** `Abdulmuizz01` (`~<Abdulmuizz/>`)  
**Repository:** https://github.com/Abdulmuizz01/slashguard  

---

## 1. Overview & Problem Statement

Decentralized insurance and parametric risk pools face a critical bottleneck: **dispute-prone, slow human claims committees** or **fragile centralized oracles**. When a DeFi protocol or vault suffers a smart contract exploit, liquidity providers need rapid, trustless settlement. 

Traditional EVM smart contracts are isolated from off-chain data—they cannot read exploit post-mortems, security disclosures, or block explorer transaction summaries on the open web.

**SlashGuard** is a standalone GenLayer Intelligent Contract that acts as an autonomous forensic claims adjudicator. When a claim is submitted with supporting evidence URLs (e.g., Rekt.news, Etherscan incident transactions, PeckShield alerts), the contract uses GenLayer's **Optimistic Democracy** to fetch the unstructured web data, cross-reference both sources against the policy's natural-language parameters, and reach strict validator consensus before liquidating payouts.

---

## 2. Architecture & State Design

```
           Issuer/Underwriter                    Insured Beneficiary
                  │                                       │
  1. create_policy(id, beneficiary,              4. withdraw_payout()
     vault, threshold, amount)                            │
     + deposits coverage tokens                           │
                  │                                       │
                  ▼                                       │
  ┌───────────────────────────────────────────────────────┐
  │  SlashGuard Intelligent Contract (GenVM)               │
  │                                                        │
  │  State:                                                │
  │  • policies: TreeMap[str, str]         (JSON blobs)    │
  │  • approved_payouts: TreeMap[str, u256] (beneficiary)  │
  │  • issuer: str           (authorized underwriter)      │
  │  • total_underwritten: u256                            │
  │                                                        │
  │  Guards:                                               │
  │  • Issuer-only policy creation (authorization)         │
  │  • Funded coverage (msg.value >= coverage_amount)      │
  │  • Trusted domain whitelist (urllib.parse)              │
  │  • Independent source enforcement (domain1 != domain2) │
  └───────────────────────┬────────────────────────────────┘
                          │
      2. submit_claim(policy_id, url_1, url_2)
                          │
          ┌───────────────┴───────────────┐
          ▼                               ▼
  ┌─────────────────┐           ┌─────────────────┐
  │ Validator Node A │           │ Validator Node B │
  │ • web.render()   │           │ • web.render()   │
  │ • exec_prompt()  │           │ • exec_prompt()  │
  │ • CONFIRMED      │           │ • CONFIRMED      │
  └────────┬─────────┘           └────────┬─────────┘
           └───────────────┬──────────────┘
                           ▼
       gl.eq_principle.strict_eq() Consensus
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
         CONFIRMED                  REJECTED
     • Credit beneficiary       • Policy stays active
     • Deactivate policy        • Issuer can cancel
     • Beneficiary withdraws      and reclaim deposit
```

### Collateral Lifecycle

Every policy has a clear, safe exit for locked funds:

| Policy State | Collateral Path |
|---|---|
| Created, no claim | Issuer calls `cancel_policy` → refund |
| Claim rejected | Issuer calls `cancel_policy` → refund |
| Claim confirmed | Beneficiary calls `withdraw_payout` → settlement |
| Already cancelled | No action possible (funds already released) |

---

## 3. Key Technical Features & GenVM Compliance

### A. Issuer Authorization & Funded Coverage
Only the contract deployer (issuer/underwriter) can create policies. Policy creation is a **payable** function requiring the issuer to deposit the full coverage amount in native tokens, ensuring the pool is always fully collateralized.

### B. Separate Beneficiary Model
The issuer designates a separate **beneficiary** address when creating a policy. Confirmed claims pay the beneficiary—not the issuer—making this a true insurance primitive rather than a self-refunding deposit.

### C. Trusted Domain Whitelist & Independence Check
Before validators spend gas on LLM consensus, the contract validates evidence URLs at the Python level using `urllib.parse`. Both URLs must originate from different root domains on a hardcoded whitelist of authoritative Web3 security sources (e.g., `rekt.news`, `etherscan.io`, `peckshield.com`).

### D. Strict Non-Deterministic Isolation
All web access (`gl.nondet.web.render`) and LLM executions (`gl.nondet.exec_prompt`) are encapsulated within an isolated helper function (`evaluate_exploit`) without referencing `self.*` storage. Local variables are captured cleanly before entering the nondet block.

### E. Equivalence Principle & Hallucination Defense
Prompt outputs are sanitized and parsed into strict binary categorical states (`CONFIRMED` vs `REJECTED`). Consensus is enforced via `gl.eq_principle.strict_eq()`, guaranteeing unanimous agreement across validators before state mutation.

### F. Pull-Over-Push Settlement with Re-entrancy Guard
Approved claims credit the beneficiary's ledger in `approved_payouts`. The `withdraw_payout` function zeros the balance **before** executing `emit_transfer`, preventing re-entrancy attacks.

### G. Safe Cancellation & Refund Path
The `cancel_policy` function allows the issuer to reclaim locked collateral for policies that were never confirmed—including policies with rejected claims. Cancellation is blocked once a claim is confirmed (funds already allocated to beneficiary).

---

## 4. How to Test in GenLayer Studio

1. Open **[GenLayer Studio](https://studio.genlayer.com)** and create a new contract with `contract.py`.
2. **Deploy** the `SlashGuard` contract with an `initial_pool_name` (e.g., `"SlashGuard Pool"`).
3. **Create Policy** (set a `value` in the value field to fund the coverage):
   * `policy_id`: `"POL-AAVE-001"`
   * `beneficiary`: `"0x<beneficiary_address>"`
   * `target_vault`: `"Aave V3"`
   * `min_loss_usd`: `500000`
   * `coverage_amount`: `100000`
4. **Test Valid Claim (Confirmed)**:
   * Call `submit_claim` with two URLs from different trusted domains reporting an authentic exploit on Aave exceeding $500,000.
   * Observe validators rotate through `evaluate_exploit` to reach consensus on `"CONFIRMED"`.
   * Check `check_approved_payout(beneficiary_address)` to see the balance ready for withdrawal.
5. **Test Invalid Claim (Rejected)**:
   * Pass unrelated articles or minor non-exploit bug reports.
   * Observe validators reach consensus on `"REJECTED"`.
   * The issuer can then call `cancel_policy` to reclaim the locked collateral.
6. **Withdraw Payout** (as the beneficiary):
   * Call `withdraw_payout()` to settle the approved balance via native token transfer.
7. **Cancel Policy** (as the issuer):
   * Call `cancel_policy("POL-AAVE-001")` to reclaim deposited collateral from an unclaimed or rejected policy.
