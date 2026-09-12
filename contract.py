# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json
import re
from urllib.parse import urlparse

# A hardcoded set of trusted, authoritative security domains
TRUSTED_DOMAINS = {
    "rekt.news",
    "etherscan.io",
    "peckshield.com",
    "certik.com",
    "halborn.com",
    "blocksec.com",
    "x.com",
    "twitter.com"
}

# Maximum number of claim attempts per policy before it auto-locks
MAX_CLAIM_ATTEMPTS = 3

# Allowed characters for target_vault to prevent prompt injection
VAULT_NAME_PATTERN = re.compile(r'^[A-Za-z0-9 \-\.]+$')

class SlashGuard(gl.Contract):
    """
    SlashGuard: Autonomous Parametric DeFi Exploit Escrow
    """
    pool_name: str
    policies: TreeMap[str, str]
    approved_payouts: TreeMap[str, u256]
    total_underwritten: u256
    issuer: str

    def __init__(self, initial_pool_name: str):
        self.pool_name = initial_pool_name
        self.total_underwritten = u256(0)
        self.issuer = gl.message.sender_address.as_hex

    @gl.public.write.payable
    def create_policy(self, policy_id: str, beneficiary: str, target_vault: str, min_loss_usd: int, coverage_amount: int) -> None:
        if gl.message.sender_address.as_hex != self.issuer:
            raise gl.vm.UserError("Unauthorized: Only the designated issuer/underwriter can create policies.")
        if policy_id in self.policies:
            raise gl.vm.UserError("Policy ID already exists.")
        if coverage_amount <= 0 or min_loss_usd <= 0:
            raise gl.vm.UserError("Coverage amount and min loss threshold must be positive.")

        # FIX 1: Strict equality prevents overpayment lock
        if gl.message.value != u256(coverage_amount):
            raise gl.vm.UserError("Deposit must exactly match the coverage amount.")

        # FIX 2: Sanitize target_vault to prevent prompt injection
        if not target_vault or len(target_vault) > 32 or not VAULT_NAME_PATTERN.match(target_vault):
            raise gl.vm.UserError("Invalid vault name. Use only alphanumeric characters, spaces, hyphens, and dots (max 32 chars).")

        # FIX 3: Normalize beneficiary address to lowercase for consistent lookups
        normalized_beneficiary = beneficiary.strip().lower()
        if not normalized_beneficiary:
            raise gl.vm.UserError("Beneficiary address cannot be empty.")
        if not re.match(r'^0x[a-f0-9]{40}$', normalized_beneficiary):
            raise gl.vm.UserError("Invalid beneficiary address format.")

        policy_data = {
            "policyholder": normalized_beneficiary,
            "vault_protocol": target_vault,
            "min_loss_usd": min_loss_usd,
            "coverage_amount": coverage_amount,
            "is_active": True,
            "claim_status": "NONE",
            "claim_attempts": 0
        }

        self.policies[policy_id] = json.dumps(policy_data)
        current_total = int(self.total_underwritten)
        self.total_underwritten = u256(current_total + coverage_amount)

    @gl.public.write
    def submit_claim(self, policy_id: str, evidence_url_1: str, evidence_url_2: str) -> str:
        raw_policy = self.policies.get(policy_id, "")
        if not raw_policy:
            raise gl.vm.UserError("Policy does not exist.")

        policy = json.loads(raw_policy)
        if not policy.get("is_active", False):
            raise gl.vm.UserError("Policy is no longer active or already settled.")

        if gl.message.sender_address.as_hex.lower() != policy["policyholder"]:
            raise gl.vm.UserError("Only the beneficiary can submit a claim.")

        # FIX 4: Enforce maximum claim attempts to prevent infinite replay attacks
        attempts = int(policy.get("claim_attempts", 0))
        if attempts >= MAX_CLAIM_ATTEMPTS:
            raise gl.vm.UserError("Maximum claim attempts exceeded. Issuer may cancel to release collateral.")

        url_1 = evidence_url_1.strip()
        url_2 = evidence_url_2.strip()

        if url_1 == url_2:
            raise gl.vm.UserError("Evidence sources must be two distinct URLs.")

        # Verify genuinely independent and authoritative sources
        domain1 = urlparse(url_1).netloc.lower().replace("www.", "")
        domain2 = urlparse(url_2).netloc.lower().replace("www.", "")

        if domain1 == domain2:
            raise gl.vm.UserError("Evidence must come from independent domains.")

        if domain1 not in TRUSTED_DOMAINS or domain2 not in TRUSTED_DOMAINS:
            raise gl.vm.UserError(f"Evidence URLs must be from authoritative trusted domains (e.g., {', '.join(list(TRUSTED_DOMAINS)[:3])})")

        target_protocol = str(policy["vault_protocol"])
        loss_threshold = int(policy["min_loss_usd"])

        def evaluate_exploit() -> str:
            try:
                raw_report_1 = gl.nondet.web.render(url_1, mode='html')
                raw_report_2 = gl.nondet.web.render(url_2, mode='html')
            except Exception:
                return "REJECTED"

            clean_report_1 = str(raw_report_1)[:4000]
            clean_report_2 = str(raw_report_2)[:4000]

            prompt = f"""
            Analyze these two authoritative exploit reports for {target_protocol}.
            Threshold: {loss_threshold} USD.

            Source 1 ({domain1}): {clean_report_1}
            Source 2 ({domain2}): {clean_report_2}

            Did a severe exploit occur on {target_protocol} exceeding the loss threshold?
            Return strictly a JSON object: {{"status": "CONFIRMED"}} or {{"status": "REJECTED"}}.
            """

            raw_output = gl.nondet.exec_prompt(prompt).strip()
            try:
                cleaned = raw_output.replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned)
                verdict = data.get("status", "REJECTED").upper()
                if verdict in ["CONFIRMED", "REJECTED"]:
                    return verdict
                return "REJECTED"
            except Exception:
                return "REJECTED"

        consensus_verdict = gl.eq_principle.strict_eq(evaluate_exploit)

        # Increment claim attempts regardless of outcome
        policy["claim_attempts"] = attempts + 1

        if consensus_verdict == "CONFIRMED":
            policyholder = str(policy["policyholder"])
            payout = int(policy["coverage_amount"])

            current_approved = int(self.approved_payouts.get(policyholder, u256(0)))
            self.approved_payouts[policyholder] = u256(current_approved + payout)

            policy["is_active"] = False
            policy["claim_status"] = "CONFIRMED"
            self.policies[policy_id] = json.dumps(policy)

            # FIX 5: Decrement total_underwritten on confirmation
            current_total = int(self.total_underwritten)
            self.total_underwritten = u256(current_total - payout)

            return "CLAIM_CONFIRMED_AND_ESCROWED"
        else:
            policy["claim_status"] = "REJECTED"
            self.policies[policy_id] = json.dumps(policy)
            return "CLAIM_REJECTED"

    @gl.public.write
    def withdraw_payout(self) -> int:
        caller = gl.message.sender_address
        # FIX 6: Normalize caller address to lowercase for consistent lookup
        caller_hex = caller.as_hex.lower()

        current_amount = self.approved_payouts.get(caller_hex, u256(0))
        if current_amount <= u256(0):
            raise gl.vm.UserError("No approved payouts available.")

        if current_amount > self.balance:
            raise gl.vm.UserError("Insufficient contract balance to cover payout.")

        # Clear the approved balance before transferring (prevent re-entrancy)
        self.approved_payouts[caller_hex] = u256(0)

        # Settle the payout by transferring GenLayer native tokens
        gl.get_contract_at(caller).emit_transfer(value=current_amount, on="finalized")

        return int(current_amount)

    @gl.public.write
    def approve_cancellation(self, policy_id: str) -> None:
        raw_policy = self.policies.get(policy_id, "")
        if not raw_policy:
            raise gl.vm.UserError("Policy does not exist.")
        
        policy = json.loads(raw_policy)
        if gl.message.sender_address.as_hex.lower() != policy["policyholder"]:
            raise gl.vm.UserError("Only the beneficiary can approve cancellation.")
            
        policy["cancellation_approved"] = True
        self.policies[policy_id] = json.dumps(policy)

    @gl.public.write
    def cancel_policy(self, policy_id: str) -> int:
        if gl.message.sender_address.as_hex != self.issuer:
            raise gl.vm.UserError("Unauthorized: Only the designated issuer/underwriter can cancel policies.")

        raw_policy = self.policies.get(policy_id, "")
        if not raw_policy:
            raise gl.vm.UserError("Policy does not exist.")

        policy = json.loads(raw_policy)
        if not policy.get("is_active", False):
            raise gl.vm.UserError("Policy is no longer active.")

        if policy.get("claim_status") not in ("NONE", "REJECTED"):
            raise gl.vm.UserError("Cannot cancel a policy with a confirmed or pending claim.")
            
        attempts = int(policy.get("claim_attempts", 0))
        if not (policy.get("cancellation_approved") == True or attempts >= MAX_CLAIM_ATTEMPTS):
            raise gl.vm.UserError("Cancellation requires beneficiary approval or exhausted claim attempts.")

        coverage_amount = int(policy["coverage_amount"])

        policy["is_active"] = False
        policy["claim_status"] = "CANCELLED"
        self.policies[policy_id] = json.dumps(policy)

        current_total = int(self.total_underwritten)
        self.total_underwritten = u256(current_total - coverage_amount)

        gl.get_contract_at(gl.message.sender_address).emit_transfer(value=u256(coverage_amount), on="finalized")

        return coverage_amount

    @gl.public.view
    def get_pool_name(self) -> str:
        return self.pool_name

    @gl.public.view
    def get_policy(self, policy_id: str) -> str:
        return self.policies.get(policy_id, "")

    @gl.public.view
    def check_approved_payout(self, user: str) -> int:
        return int(self.approved_payouts.get(user.lower(), u256(0)))
