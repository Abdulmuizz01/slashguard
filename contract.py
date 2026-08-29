# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json

class SlashGuard(gl.Contract):
    """
    SlashGuard: Autonomous Parametric DeFi Exploit Escrow
    """
    pool_name: str
    policies: TreeMap[str, str]
    approved_payouts: TreeMap[str, u256]
    total_underwritten: u256

    def __init__(self, initial_pool_name: str):
        self.pool_name = initial_pool_name
        self.total_underwritten = u256(0)

    @gl.public.write
    def create_policy(self, policy_id: str, target_vault: str, min_loss_usd: int, coverage_amount: int) -> None:
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
            "claim_status": "NONE"
        }
        
        self.policies[policy_id] = json.dumps(policy_data)
        current_total = int(self.total_underwritten)
        self.total_underwritten = u256(current_total + coverage_amount)

    @gl.public.write
    def submit_claim(self, policy_id: str, evidence_url_1: str, evidence_url_2: str) -> str:
        raw_policy = self.policies.get(policy_id, "")
        if not raw_policy:
            raise Exception("Policy does not exist.")
        
        policy = json.loads(raw_policy)
        if not policy.get("is_active", False):
            raise Exception("Policy is no longer active or already settled.")
        
        if evidence_url_1.strip() == evidence_url_2.strip():
            raise Exception("Evidence sources must be two distinct URLs.")

        target_protocol = str(policy["vault_protocol"])
        loss_threshold = int(policy["min_loss_usd"])
        url_1 = str(evidence_url_1)
        url_2 = str(evidence_url_2)

        def evaluate_exploit() -> str:
            raw_report_1 = gl.nondet.web.render(url_1, mode='html')
            raw_report_2 = gl.nondet.web.render(url_2, mode='html')

            clean_report_1 = str(raw_report_1)[:4000]
            clean_report_2 = str(raw_report_2)[:4000]

            prompt = f"""
            Analyze these two exploit reports for {target_protocol}.
            Threshold: ${loss_threshold:,} USD.

            Source 1: {clean_report_1}
            Source 2: {clean_report_2}

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

        if consensus_verdict == "CONFIRMED":
            policyholder = str(policy["policyholder"])
            payout = int(policy["coverage_amount"])
            
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
        caller = str(gl.message.sender)
        current_amount = int(self.approved_payouts.get(caller, u256(0)))
        if current_amount <= 0:
            raise Exception("No approved payouts available.")
        self.approved_payouts[caller] = u256(0)
        return current_amount

    @gl.public.view
    def get_pool_name(self) -> str:
        return self.pool_name

    @gl.public.view
    def get_policy(self, policy_id: str) -> str:
        return self.policies.get(policy_id, "")

    @gl.public.view
    def check_approved_payout(self, user: str) -> int:
        return int(self.approved_payouts.get(user, u256(0)))
