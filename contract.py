# { "Depends": "py-genlayer:test" }
from genlayer import *
import json

class SlashGuard(gl.Contract):
    """
    SlashGuard: Autonomous Parametric DeFi Exploit Escrow
    
    A standalone GenLayer Intelligent Contract that validates smart contract exploits
    using multi-source web evidence and decentralized AI validator consensus under
    Optimistic Democracy.
    """
    policies: TreeMap[str, str]
    approved_payouts: TreeMap[str, u256]
    total_underwritten: u256

    def __init__(self):
        self.total_underwritten = u256(0)

    @gl.public.write
    def create_policy(self, policy_id: str, target_vault: str, min_loss_usd: int, coverage_amount: int) -> None:
        """
        Creates an exploit contingency policy for a specified protocol vault.
        """
        if policy_id in self.policies:
            raise Exception("Policy ID already exists.")
        if coverage_amount <= 0 or min_loss_usd <= 0:
            raise Exception("Coverage amount and min loss threshold must be positive.")

        caller = str(gl.message.sender)

        policy_data = {
            "policyholder": caller,
            "vault_protocol": target_vault,
            "min_loss_usd": min_loss_usd,
            "coverage_amount": coverage_amount,
            "is_active": True,
            "claim_status": "NONE"  # NONE | CONFIRMED | REJECTED
        }
        
        self.policies[policy_id] = json.dumps(policy_data)
        current_total = int(self.total_underwritten)
        self.total_underwritten = u256(current_total + coverage_amount)

    @gl.public.write
    def submit_claim(self, policy_id: str, evidence_url_1: str, evidence_url_2: str) -> str:
        """
        Submits two independent web evidence sources for exploit adjudication.
        Triggers GenLayer non-deterministic web fetching and LLM forensic consensus.
        """
        raw_policy = self.policies.get(policy_id, "")
        if not raw_policy:
            raise Exception("Policy does not exist.")
        
        policy = json.loads(raw_policy)
        if not policy.get("is_active", False):
            raise Exception("Policy is no longer active or already settled.")
        
        # Corroboration Guard: Evidence must come from two distinct URLs
        if evidence_url_1.strip() == evidence_url_2.strip():
            raise Exception("Evidence sources must be two distinct URLs.")
        
        if not (evidence_url_1.startswith("http") and evidence_url_2.startswith("http")):
            raise Exception("Invalid evidence URL format.")

        # Capture state into local variables before nondet isolation
        target_protocol = str(policy["vault_protocol"])
        loss_threshold = int(policy["min_loss_usd"])
        url_1 = str(evidence_url_1)
        url_2 = str(evidence_url_2)

        # Non-deterministic evaluation block (isolated from contract state)
        def evaluate_exploit() -> str:
            # 1. Fetch web pages independently via GenLayer nondet web rendering
            raw_report_1 = gl.nondet.web.render(url_1, mode='html')
            raw_report_2 = gl.nondet.web.render(url_2, mode='html')

            # Clean and truncate text payload to prevent token overflow
            clean_report_1 = str(raw_report_1)[:5000]
            clean_report_2 = str(raw_report_2)[:5000]

            prompt = f"""
            You are an expert on-chain forensic security auditor acting as a GenLayer consensus validator.
            Analyze the following two web reports to determine if a genuine smart contract exploit or vault drain occurred.

            TARGET PROTOCOL: {target_protocol}
            MINIMUM EXPLOIT LOSS THRESHOLD: ${loss_threshold:,} USD

            --- EVIDENCE SOURCE 1 ---
            {clean_report_1}

            --- EVIDENCE SOURCE 2 ---
            {clean_report_2}

            FORENSIC RULES:
            1. Both sources must corroborate that a security incident / smart contract exploit affected '{target_protocol}'.
            2. The estimated financial drain or capital loss must meet or exceed ${loss_threshold:,} USD.
            3. Routine market volatility, user phishing, or unrelated exploits must be REJECTED.
            4. If evidence is unverified, missing, or contradictory, output REJECTED.

            Return strictly a valid JSON object matching this schema:
            {{"status": "CONFIRMED"}} or {{"status": "REJECTED"}}
            """

            raw_ai_output = gl.nondet.exec_prompt(prompt).strip()

            # Normalize JSON formatting across validators
            try:
                cleaned_output = raw_ai_output.replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned_output)
                verdict = data.get("status", "REJECTED").upper()
                if verdict in ["CONFIRMED", "REJECTED"]:
                    return verdict
                return "REJECTED"
            except Exception:
                return "REJECTED"

        # Reach validator consensus via strict equivalence
        consensus_verdict = gl.eq_principle.strict_eq(evaluate_exploit)

        # State transition based on consensus outcome
        if consensus_verdict == "CONFIRMED":
            policyholder = str(policy["policyholder"])
            payout = int(policy["coverage_amount"])
            
            # Pull-over-Push accounting ledger update
            current_approved = int(self.approved_payouts.get(policyholder, u256(0)))
            self.approved_payouts[policyholder] = u256(current_approved + payout)
            
            policy["is_active"] = False
            policy["claim_status"] = "CONFIRMED"
            self.policies[policy_id] = json.dumps(policy)
            return "CLAIM_CONFIRMED_AND_ESCROWED"
        else:
            policy["claim_status"] = "REJECTED"
            self.policies[policy_id] = json.dumps(policy)
            return "CLAIM_REJECTED"

    @gl.public.write
    def withdraw_payout(self) -> int:
        """
        Pull-Over-Push pattern: Allows policyholders to safely withdraw approved claim balances.
        """
        caller = str(gl.message.sender)
        current_amount = int(self.approved_payouts.get(caller, u256(0)))
        
        if current_amount <= 0:
            raise Exception("No approved payouts available for withdrawal.")
        
        # Zero out balance to prevent reentrancy and double withdrawal
        self.approved_payouts[caller] = u256(0)
        return current_amount

    @gl.public.view
    def get_policy(self, policy_id: str) -> str:
        """View details of a specific policy as a JSON string."""
        raw_policy = self.policies.get(policy_id, "")
        if not raw_policy:
            raise Exception("Policy not found.")
        return raw_policy

    @gl.public.view
    def check_approved_payout(self, user: str) -> int:
        """View the approved payout balance ready for withdrawal for a user."""
        return int(self.approved_payouts.get(user, u256(0)))
