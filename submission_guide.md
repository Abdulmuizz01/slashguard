# GenLayer Portal Submission Guide

When you click **"Submit a contribution"** -> **"Intelligent Contracts"** on the GenLayer Portal, copy and paste the following fields:

---

### Field 1: Title / Name
```
SlashGuard: Web-Grounded Parametric Exploit Escrow
```

---

### Field 2: Short Summary / Tagline
```
Autonomous DeFi insurance escrow that liquidates exploit payouts through multi-source web evidence and GenVM Optimistic Democracy consensus.
```

---

### Field 3: Contract Source Code
Copy the entire content from [contract.py](file:///C:/Users/USER/.gemini/antigravity/brain/a7c5b56c-df28-4215-b9bc-48a297842fca/contract.py).

---

### Field 4: Description / Technical Architecture
Copy the content from [README.md](file:///C:/Users/USER/.gemini/antigravity/brain/a7c5b56c-df28-4215-b9bc-48a297842fca/README.md).

---

### Field 5: GitHub Repository URL
```
https://github.com/Abdulmuiz01/slashguard
```

---

### Field 6: How to Test (Reviewer Instructions)
```markdown
1. Open GenLayer Studio (https://studio.genlayer.com).
2. Paste `contract.py` and click Deploy.
3. Call `create_policy("POL-AAVE-001", "Aave V3", 500000, 100000)`.
4. Call `submit_claim("POL-AAVE-001", "<URL_1>", "<URL_2>")` with two exploit incident report URLs.
5. Observe GenLayer validators reach strict consensus (`gl.eq_principle.strict_eq`) on the normalized verdict.
6. Call `check_approved_payout(user_address)` and `withdraw_payout()` to verify the pull-over-push settlement.
```
