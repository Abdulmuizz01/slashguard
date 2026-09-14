# SlashGuard: Web-Grounded Parametric Exploit Escrow

**Submission Track:** Builder — Intelligent Contracts  
**Author:** `Abdulmuizz01` (`~<Abdulmuizz/>`)  
**Repository:** https://github.com/Abdulmuizz01/slashguard  

---

## 1. Overview & Problem Statement

Decentralized insurance and parametric risk pools face a critical bottleneck: **dispute-prone, slow human claims committees** or **fragile centralized oracles**. When a DeFi protocol or vault suffers a smart contract exploit, liquidity providers need rapid, trustless settlement. 

Traditional EVM smart contracts are isolated from off-chain data—they cannot read exploit post-mortems, security disclosures, or block explorer transaction summaries on the open web.

**SlashGuard** is a standalone GenLayer Intelligent Contract that acts as an autonomous forensic claims adjudicator. When a claim is submitted with supporting evidence URLs (e.g., Rekt.news, Etherscan incident transactions, PeckShield alerts), the contract uses GenLayer's **Optimistic Democracy** to fetch unstructured web data, cross-reference both sources against the policy's natural-language parameters, and reach strict validator consensus before liquidating payouts.

---

## 2. Architecture & State Design

```
           Issuer/Underwriter                    Insured Beneficiary
                  │                                       │
  1. create_policy(id, beneficiary,              2. submit_claim(id, url_1, url_2)
     vault, threshold, amount)                   [Only beneficiary can submit]
     + deposits exact coverage tokens                     │
                  │                                       │
                  ▼                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │  SlashGuard Intelligent Contract (GenVM)                                │
  │                                                                        │
  │  State:                                                                │
  │  • policies: TreeMap[str, str]         (JSON blobs)                    │
  │  • approved_payouts: TreeMap[str, u256] (beneficiary payouts ledger)   │
  │  • issuer: str           (authorized underwriter)                      │
  │  • total_underwritten: u256                                            │
  │                                                                        │
  │  Security Guards:                                                      │
  │  • Issuer-only policy creation                                         │
  │  • Strict deposit matching (msg.value == coverage_amount)               │
  │  • Canonical beneficiary validation (strict ^0x[a-f0-9]{40}$)           │
  │  • Beneficiary-only claim submission (stops 3rd-party griefing)         │
  │  • Attempt limit: max 3 attempts per policy                            │
  │  • Mutual cancellation: approve_cancellation() or exhausted attempts   │
  │  • Strict URL parsing: HTTPS only, no credentials, no custom ports     │
  │  • Trusted domain whitelist + canonical alias mapping (e.g. x.com)     │
  │  • Independent source check (host1 != host2)                           │
  └───────────────────────────────────┬────────────────────────────────────┘
                                      │
                                      ▼
                      gl.eq_principle.strict_eq() Consensus
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                    CONFIRMED                  REJECTED
                • Credit beneficiary       • Attempt counter increments
                • Deactivate policy        • Policy remains active
                • Beneficiary calls        • Beneficiary can retry (up to 3)
                  withdraw_payout()          or call approve_cancellation()
```

### Collateral & Policy Lifecycle

Every policy enforces a deterministic lifecycle with zero stranded funds and strong rug-pull protection:

| Policy State | Active? | Allowed Actions | Exit Path |
|---|---|---|---|
| **Active (0-2 attempts)** | Yes | Beneficiary calls `submit_claim` or `approve_cancellation` | Coverage active; issuer cannot unilaterally cancel |
| **Claim Confirmed** | No | Beneficiary calls `withdraw_payout` | Native payout transferred to beneficiary |
| **Claim Rejected (< 3 attempts)** | Yes | Beneficiary retries `submit_claim` or calls `approve_cancellation` | Coverage preserved for beneficiary |
| **Cancellation Approved** | Yes | Issuer calls `cancel_policy` | Mutual consent: 100% deposit refunded to issuer |
| **Attempts Exhausted (>= 3)** | Yes | Issuer calls `cancel_policy` | Deadlock prevented: 100% deposit refunded to issuer |
| **Cancelled** | No | None | Collateral already returned |

---

## 3. Key Technical Features & GenVM Compliance

### A. Strict Issuer Authorization & Funded Coverage
Only the contract deployer (`self.issuer`) can create policies. Policy creation is **payable** and requires exact funding (`gl.message.value == u256(coverage_amount)`). This prevents overpayment traps and guarantees the contract holds 100% of underwritten collateral.

### B. Canonical Beneficiary Validation & Separation
The beneficiary is explicitly decoupled from the issuer. Beneficiary addresses are strictly validated against `^0x[a-f0-9]{40}$` and normalized to lowercase. Zero-address and issuer-as-beneficiary self-insuring loops are blocked at creation time.

### C. Griefing & Rug-Pull Prevention
* **Beneficiary-Only Claims:** `submit_claim` enforces that `gl.message.sender_address` equals the stored `policyholder`. External third parties cannot call the contract to waste claim attempts.
* **Mutual Consent Cancellation:** The issuer **cannot** arbitrarily cancel an active policy to rug-pull coverage. Cancellation requires either explicit beneficiary consent (`approve_cancellation`) or exhaustion of all 3 claim attempts.

### D. Strict URL Parsing, Domain Whitelist & Canonical Aliasing
Evidence URLs are parsed strictly using `urllib.parse`:
- Must strictly use the `https` scheme.
- Embedded credentials (`user:pass@host`) and non-standard ports are rejected.
- Validates the parsed `hostname` (not raw `netloc`) against `TRUSTED_DOMAINS` (`rekt.news`, `etherscan.io`, `peckshield.com`, `certik.com`, `halborn.com`, `blocksec.com`, `x.com`, `twitter.com`).
- Canonical domain aliases (`twitter.com` -> `x.com`) prevent cross-submitting the same source under different hostnames.

### E. GenVM Runtime State & Balance Semantics
- **State Storage:** GenVM automatically instantiates persistent storage proxies for class-annotated `TreeMap` instances (`policies` and `approved_payouts`). Explicit manual reassignment in `__init__` (e.g. `self.policies = TreeMap()`) is strictly avoided as it overwrites GenVM's internal storage proxy and causes deployment failure.
- **Balance Property:** `self.balance` is a built-in GenVM contract property representing the contract's native token balance, utilized to verify solvency prior to dispatching transfers.

### F. Trust Model & Fallback Behavior
- **Authority Whitelist:** The contract trusts established forensic audit firms and block explorers. Validators do not accept random blogs or social media mirrors.
- **Graceful Error Fallbacks:** If a source website is temporarily unreachable or throws a 404/500 during `gl.nondet.web.render`, or if an LLM response is unparseable, the validator execution safely catches the exception and returns `"REJECTED"` rather than causing an unhandled runtime error.
- **Consensus Failure vs. Rejection:** If validators disagree on an ambiguous report (some return `CONFIRMED` while others return `REJECTED`), `gl.eq_principle.strict_eq()` does not reach consensus and the transaction reverts, preserving state without consuming claim attempts. A claim attempt is consumed only when validators unanimously agree on a `REJECTED` verdict.

---

## 4. How to Test in GenLayer Studio

1. Open **[GenLayer Studio](https://studio.genlayer.com)** and deploy `contract.py` with an `initial_pool_name` (e.g., `"SlashGuard Pool"`).
2. **Create Policy** (as Issuer, attaching exact deposit `value` equal to `coverage_amount`):
   * `policy_id`: `"POL-AAVE-001"`
   * `beneficiary`: `"0x1111111111111111111111111111111111111111"`
   * `target_vault`: `"Aave V3"`
   * `min_loss_usd`: `500000`
   * `coverage_amount`: `100000`
3. **Test Claim Submission** (as Beneficiary):
   * Call `submit_claim` using two distinct trusted domain URLs (e.g. `https://rekt.news/aave-v3-incident` and `https://peckshield.com/alerts/aave-v3`).
   * Calls from non-beneficiary addresses will revert with `UserError`.
4. **Test Payout Withdrawal** (as Beneficiary, upon `CONFIRMED` consensus):
   * Call `withdraw_payout()` to receive native tokens.
5. **Test Safe Cancellation** (as Issuer):
   * Unilateral cancellation while coverage is active will revert.
   * Beneficiary can call `approve_cancellation("POL-AAVE-001")`, allowing the issuer to invoke `cancel_policy` and reclaim collateral.
   * Alternatively, if 3 claim attempts are rejected, the issuer can call `cancel_policy` to prevent trapped funds.
