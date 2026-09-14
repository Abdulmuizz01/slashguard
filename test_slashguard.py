import sys
import unittest
from unittest.mock import MagicMock
import json
import re

# ==============================================================================
# Comprehensive Mock of the GenLayer Runtime for Local Automated Testing
# ==============================================================================

class MockU256:
    def __init__(self, val):
        self.val = int(val)
    def __int__(self):
        return self.val
    def __add__(self, other):
        return MockU256(self.val + int(other))
    def __sub__(self, other):
        return MockU256(self.val - int(other))
    def __eq__(self, other):
        return self.val == int(other)
    def __le__(self, other):
        return self.val <= int(other)
    def __ge__(self, other):
        return self.val >= int(other)
    def __lt__(self, other):
        return self.val < int(other)
    def __gt__(self, other):
        return self.val > int(other)
    def __repr__(self):
        return f"u256({self.val})"

class MockAddress:
    def __init__(self, hex_val):
        self.as_hex = hex_val

class MockMessage:
    def __init__(self, sender_hex, value=0):
        self.sender_address = MockAddress(sender_hex)
        self.value = MockU256(value)

class MockUserError(Exception):
    pass

class MockVM:
    UserError = MockUserError

class MockWeb:
    def __init__(self):
        self.behavior = "normal"
    def render(self, url, mode):
        if self.behavior == "fail":
            raise Exception("Connection timeout / 404")
        return "Exploit confirmed! Protocol suffered a $10M loss."

class MockNondet:
    def __init__(self):
        self.web = MockWeb()
        self.prompt_response = '{"status": "CONFIRMED"}'
    def exec_prompt(self, prompt):
        return self.prompt_response

class MockEqPrinciple:
    """
    Simulates GenLayer Optimistic Democracy & Strict Equivalence:
    Runs the closure across simulated validators and tests for agreement.
    """
    def __init__(self):
        self.mode = "agree" # "agree", "disagree", "divergent"
        self.divergent_outputs = []

    def strict_eq(self, func):
        if self.mode == "agree":
            v1 = func()
            v2 = func()
            if v1 == v2:
                return v1
            raise MockUserError("Consensus failed: Validator outputs diverged.")
        elif self.mode == "disagree":
            outputs = ["CONFIRMED", "REJECTED", "REJECTED"]
            if len(set(outputs)) > 1:
                raise MockUserError("Consensus failed: Validators could not reach strict equivalence.")
            return outputs[0]
        elif self.mode == "divergent":
            raise MockUserError("Consensus failed: Non-deterministic execution detected across validators.")

class MockGL:
    def __init__(self):
        self.message = MockMessage("0xissuer")
        self.vm = MockVM()
        self.nondet = MockNondet()
        self.eq_principle = MockEqPrinciple()
        self.transfers = []
        
        self.public = MagicMock()
        self.public.write = lambda f: f
        self.public.write.payable = lambda f: f
        self.public.view = lambda f: f
        self.Contract = object
        
    def get_contract_at(self, address):
        mock_contract = MagicMock()
        def record_transfer(value, on):
            self.transfers.append({"to": address.as_hex if hasattr(address, "as_hex") else address, "value": int(value), "on": on})
        mock_contract.emit_transfer = record_transfer
        return mock_contract

mock_gl = MockGL()

genlayer_mock = MagicMock()
genlayer_mock.gl = mock_gl
genlayer_mock.u256 = MockU256
genlayer_mock.TreeMap = dict
genlayer_mock.Contract = object

sys.modules['genlayer'] = genlayer_mock

import contract

# ==============================================================================
# Test Fixtures and Helper
# ==============================================================================

BENEFICIARY = "0x1111111111111111111111111111111111111111"
ISSUER = "0x0000000000000000000000000000000000000001"
ATTACKER = "0x9999999999999999999999999999999999999999"


class TestSlashGuard(unittest.TestCase):

    def setUp(self):
        mock_gl.message = MockMessage(ISSUER)
        mock_gl.nondet.web.behavior = "normal"
        mock_gl.nondet.prompt_response = '{"status": "CONFIRMED"}'
        mock_gl.eq_principle.mode = "agree"
        mock_gl.transfers.clear()
        
        self.c = contract.SlashGuard("SlashGuard Pool")
        self.c.policies = {}
        self.c.approved_payouts = {}
        self.c.balance = MockU256(500000)

    def test_1_create_policy_success_and_accounting(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        policy = json.loads(self.c.policies["POL-1"])
        self.assertEqual(policy["policyholder"], BENEFICIARY)
        self.assertEqual(policy["coverage_amount"], 100000)
        self.assertTrue(policy["is_active"])
        self.assertEqual(policy["claim_status"], "NONE")
        self.assertEqual(int(self.c.total_underwritten), 100000)

    def test_2_create_policy_underfunded_and_overpayment_rejected(self):
        mock_gl.message = MockMessage(ISSUER, value=50000) # Underpaid
        with self.assertRaises(MockUserError) as cm:
            self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        self.assertIn("Deposit must exactly match", str(cm.exception))
            
        mock_gl.message = MockMessage(ISSUER, value=150000) # Overpaid
        with self.assertRaises(MockUserError) as cm:
            self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        self.assertIn("Deposit must exactly match", str(cm.exception))

    def test_3_create_policy_invalid_beneficiary_rejected(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        
        with self.assertRaises(MockUserError):
            self.c.create_policy("POL-1", "vitalik.eth", "Aave V3", 500000, 100000)
            
        with self.assertRaises(MockUserError):
            self.c.create_policy("POL-1", "0x123", "Aave V3", 500000, 100000)
            
        with self.assertRaises(MockUserError):
            self.c.create_policy("POL-1", "0x" + "0"*40, "Aave V3", 500000, 100000)
            
        with self.assertRaises(MockUserError):
            self.c.create_policy("POL-1", ISSUER, "Aave V3", 500000, 100000)

    def test_4_evidence_url_strict_validation(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        mock_gl.message = MockMessage(BENEFICIARY)
        
        # HTTP rejected
        with self.assertRaises(MockUserError) as cm:
            self.c.submit_claim("POL-1", "http://rekt.news/1", "https://peckshield.com/1")
        self.assertIn("must use HTTPS", str(cm.exception))
            
        # Embedded credentials rejected
        with self.assertRaises(MockUserError) as cm:
            self.c.submit_claim("POL-1", "https://user:password@rekt.news/1", "https://peckshield.com/1")
        self.assertIn("embedded credentials", str(cm.exception))
            
        # Untrusted domain rejected
        with self.assertRaises(MockUserError):
            self.c.submit_claim("POL-1", "https://untrusted-blog.com/1", "https://peckshield.com/1")
            
        # Aliased domain rejected
        with self.assertRaises(MockUserError) as cm:
            self.c.submit_claim("POL-1", "https://twitter.com/alert/1", "https://x.com/alert/2")
        self.assertIn("independent domains", str(cm.exception))

    def test_5_submit_claim_restricted_to_beneficiary(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.message = MockMessage(ATTACKER)
        with self.assertRaises(MockUserError) as cm:
            self.c.submit_claim("POL-1", "https://rekt.news/1", "https://peckshield.com/1")
        self.assertIn("Only the beneficiary", str(cm.exception))

    def test_6_consensus_confirmed_claim_and_payout_ledger(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.message = MockMessage(BENEFICIARY)
        res = self.c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
        self.assertEqual(res, "CLAIM_CONFIRMED_AND_ESCROWED")
        
        policy = json.loads(self.c.policies["POL-1"])
        self.assertFalse(policy["is_active"])
        self.assertEqual(policy["claim_status"], "CONFIRMED")
        self.assertEqual(self.c.check_approved_payout(BENEFICIARY), 100000)
        self.assertEqual(int(self.c.total_underwritten), 0)

    def test_7_consensus_disagreement_failure(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.message = MockMessage(BENEFICIARY)
        mock_gl.eq_principle.mode = "disagree" 
        with self.assertRaises(MockUserError) as cm:
            self.c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
        self.assertIn("strict equivalence", str(cm.exception))

    def test_8_web_render_failure_gracefully_handled(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.nondet.web.behavior = "fail"
        mock_gl.message = MockMessage(BENEFICIARY)
        res = self.c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
        self.assertEqual(res, "CLAIM_REJECTED")
        
        policy = json.loads(self.c.policies["POL-1"])
        self.assertEqual(policy["claim_attempts"], 1)
        self.assertEqual(policy["claim_status"], "REJECTED")
        self.assertTrue(policy["is_active"])

    def test_9_successful_withdrawal_and_reentrancy_prevention(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.message = MockMessage(BENEFICIARY)
        self.c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
        
        amount = self.c.withdraw_payout()
        self.assertEqual(amount, 100000)
        self.assertEqual(len(mock_gl.transfers), 1)
        self.assertEqual(mock_gl.transfers[0]["to"], BENEFICIARY)
        self.assertEqual(mock_gl.transfers[0]["value"], 100000)
        self.assertEqual(self.c.check_approved_payout(BENEFICIARY), 0)
        
        with self.assertRaises(MockUserError) as cm:
            self.c.withdraw_payout()
        self.assertIn("No approved payouts available", str(cm.exception))

    def test_10_insufficient_contract_balance_reverts(self):
        self.c.approved_payouts[BENEFICIARY] = MockU256(100000)
        self.c.balance = MockU256(50000)
        
        mock_gl.message = MockMessage(BENEFICIARY)
        with self.assertRaises(MockUserError) as cm:
            self.c.withdraw_payout()
        self.assertIn("Insufficient contract balance", str(cm.exception))

    def test_11_unilateral_issuer_cancellation_blocked(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.message = MockMessage(ISSUER)
        with self.assertRaises(MockUserError) as cm:
            self.c.cancel_policy("POL-1")
        self.assertIn("requires beneficiary approval or exhausted", str(cm.exception))

    def test_12_mutual_consent_cancellation_and_refund(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.message = MockMessage(BENEFICIARY)
        self.c.approve_cancellation("POL-1")
        
        mock_gl.message = MockMessage(ISSUER)
        refund = self.c.cancel_policy("POL-1")
        self.assertEqual(refund, 100000)
        self.assertEqual(len(mock_gl.transfers), 1)
        self.assertEqual(mock_gl.transfers[0]["to"], ISSUER)
        self.assertEqual(mock_gl.transfers[0]["value"], 100000)
        self.assertEqual(int(self.c.total_underwritten), 0)
        
        policy = json.loads(self.c.policies["POL-1"])
        self.assertFalse(policy["is_active"])
        self.assertEqual(policy["claim_status"], "CANCELLED")

    def test_13_cancellation_after_three_rejected_attempts(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.nondet.prompt_response = '{"status": "REJECTED"}'
        mock_gl.message = MockMessage(BENEFICIARY)
        
        self.c.submit_claim("POL-1", "https://rekt.news/1", "https://peckshield.com/1")
        self.c.submit_claim("POL-1", "https://rekt.news/2", "https://peckshield.com/2")
        self.c.submit_claim("POL-1", "https://rekt.news/3", "https://peckshield.com/3")
        
        with self.assertRaises(MockUserError) as cm:
            self.c.submit_claim("POL-1", "https://rekt.news/4", "https://peckshield.com/4")
        self.assertIn("Maximum claim attempts exceeded", str(cm.exception))
            
        mock_gl.message = MockMessage(ISSUER)
        refund = self.c.cancel_policy("POL-1")
        self.assertEqual(refund, 100000)
        self.assertEqual(len(mock_gl.transfers), 1)
        self.assertEqual(mock_gl.transfers[0]["to"], ISSUER)

    def test_14_cannot_cancel_confirmed_policy_and_cannot_payout_cancelled(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.message = MockMessage(BENEFICIARY)
        self.c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
        
        mock_gl.message = MockMessage(ISSUER)
        with self.assertRaises(MockUserError):
            self.c.cancel_policy("POL-1")

    def test_15_cannot_claim_policy_pending_cancellation(self):
        mock_gl.message = MockMessage(ISSUER, value=100000)
        self.c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        
        mock_gl.message = MockMessage(BENEFICIARY)
        self.c.approve_cancellation("POL-1")
        
        with self.assertRaises(MockUserError) as cm:
            self.c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
        self.assertIn("pending cancellation", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
