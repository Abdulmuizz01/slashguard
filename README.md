# SlashGuard: Web-Grounded Parametric Exploit Escrow

**Submission Track:** Builder — Intelligent Contracts  
**Author:** `~<Abdulmuizz/>`  

---

## 1. Overview & Problem Statement

Decentralized insurance and parametric risk pools face a critical bottleneck: **dispute-prone, slow human claims committees** or **fragile centralized oracles**. When a DeFi protocol or vault suffers a smart contract exploit, liquidity providers need rapid, trustless settlement. 

Traditional EVM smart contracts are isolated from off-chain data—they cannot read exploit post-mortems, security disclosures, or block explorer transaction summaries on the open web.

**SlashGuard** is a standalone GenLayer Intelligent Contract that acts as an autonomous forensic claims adjudicator. When a claim is submitted with supporting evidence URLs (e.g., Rekt.news, Etherscan incident transactions, PeckShield alerts), the contract uses GenLayer's **Optimistic Democracy** to fetch the unstructured web data, cross-reference both sources against the policy's natural-language parameters, and reach strict validator consensus before liquidating payouts.

---

## 2. Architecture & State Design

```
                     ┌────────────────────────────────┐
                     │ Policyholder / Vault Depositor │
                     └───────────────┬────────────────┘
                                     │
                 1. submit_claim(policy_id, url_1, url_2)
                                     ▼
         ┌────────────────────────────────────────────────────────┐
         │ SlashGuard Intelligent Contract (GenVM)                │
         │                                                        │
         │  • Enforces Corroboration Guard (distinct URLs)        │
         │  • Isolates State -> Enters Nondet Execution Block     │
         └───────────────────────────┬────────────────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
     ┌───────────────────────┐               ┌───────────────────────┐
     │   Validator Node A    │               │   Validator Node B    │
     │  • gl.nondet.web()    │               │  • gl.nondet.web()    │
     │  • gl.nondet.prompt() │               │  • gl.nondet.prompt() │
     │  • Returns: CONFIRMED │               │  • Returns: CONFIRMED │
     └───────────┬───────────┘               └───────────┬───────────┘
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     │
                                     ▼
             ┌───────────────────────────────────────────────┐
             │    gl.eq_principle.strict_eq() Consensus      │
             └───────────────────────┬───────────────────────┘
                                     │
                        [ Agreement: CONFIRMED ]
                                     │
                                     ▼
     ┌───────────────────────────────────────────────────────────────┐
     │ State Transition & Pull-over-Push Settlement                  │
     │  • self.approved_payouts[policyholder] += coverage_amount     │
     │  • self.policies[policy_id].is_active = False                 │
     └───────────────────────────────┬───────────────────────────────┘
                                     │
                         2. withdraw_payout()
                                     ▼
                     ┌────────────────────────────────┐
                     │  Claimant Receives Payout      │
                     └────────────────────────────────┘
```

---

## 3. Key Technical Features & GenVM Compliance

### A. Strict Non-Deterministic Isolation
GenVM requires all web access (`gl.nondet.web.render`) and LLM executions (`gl.nondet.exec_prompt`) to be strictly encapsulated within an isolated helper function (`evaluate_exploit`) without referencing `self.*` storage. Local variables are captured cleanly before entering the nondet block.

### B. Multi-Source Corroboration Guard
To prevent single-source prompt injection or spoofed URLs, the contract natively enforces that claims contain two distinct URL endpoints. Validators cross-examine both sources to ensure independent confirmation of the exploit.

### C. Equivalence Principle & Hallucination Defense
To eliminate non-deterministic LLM formatting drift across validators, prompt outputs are sanitized and parsed into strict binary categorical states (`CONFIRMED` vs `REJECTED`). Consensus is enforced via `gl.eq_principle.strict_eq()`, guaranteeing unanimous agreement across validator models before state mutation.

### D. Pull-Over-Push Accounting Security
Approved claims credit the claimant's ledger in `approved_payouts` rather than executing direct external pushes inside the consensus loop, mitigating reentrancy risks and adhering to standard Web3 security best practices.

---

## 4. How to Test in GenLayer Studio

1. Open **[GenLayer Studio](https://studio.genlayer.com)** and create a new contract with `contract.py`.
2. **Deploy** the `SlashGuard` contract.
3. **Create Policy**:
   * `policy_id`: `"POL-AAVE-001"`
   * `target_vault`: `"Aave V3"`
   * `min_loss_usd`: `500000`
   * `coverage_amount`: `100000`
4. **Test Valid Claim (Confirmed)**:
   * Pass two URLs reporting an authentic exploit on Aave exceeding $500,000.
   * Observe validators rotate through `evaluate_exploit` to reach consensus on `"CONFIRMED"`.
   * Check `check_approved_payout(user_address)` to see the 100,000 balance ready for withdrawal.
5. **Test Invalid Claim (Rejected)**:
   * Pass unrelated articles or minor non-exploit bug reports.
   * Observe validators reach consensus on `"REJECTED"`, leaving policy inactive and funds safe.
6. **Withdraw Payout**:
   * Call `withdraw_payout()` to settle the approved balance.
