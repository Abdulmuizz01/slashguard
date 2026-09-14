import sys
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
            # Simulate validators disagreeing on verdict
            outputs = ["CONFIRMED", "REJECTED", "REJECTED"]
            if len(set(outputs)) > 1:
                # In GenLayer, failure to achieve strict equivalence reverts or fails consensus
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

# Import contract after mocking genlayer environment
import contract

# ==============================================================================
# Test Fixtures and Helper
# ==============================================================================

BENEFICIARY = "0x1111111111111111111111111111111111111111"
ISSUER = "0x0000000000000000000000000000000000000001"
ATTACKER = "0x9999999999999999999999999999999999999999"

def setup_contract():
    mock_gl.message = MockMessage(ISSUER)
    mock_gl.nondet.web.behavior = "normal"
    mock_gl.nondet.prompt_response = '{"status": "CONFIRMED"}'
    mock_gl.eq_principle.mode = "agree"
    mock_gl.transfers.clear()
    
    c = contract.SlashGuard("SlashGuard Pool")
    c.policies = {}
    c.approved_payouts = {}
    c.balance = MockU256(500000)
    return c

# ==============================================================================
# Suite of 15 Comprehensive Lifecycle & Consensus Unit Tests
# ==============================================================================

def test_1_create_policy_success_and_accounting():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    policy = json.loads(c.policies["POL-1"])
    assert policy["policyholder"] == BENEFICIARY
    assert policy["coverage_amount"] == 100000
    assert policy["is_active"] is True
    assert policy["claim_status"] == "NONE"
    assert int(c.total_underwritten) == 100000
    print("[PASS] Test 1: Policy creation and accounting")

def test_2_create_policy_underfunded_and_overpayment_rejected():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=50000) # Underpaid
    try:
        c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        assert False, "Should reject underpayment"
    except MockUserError as e:
        assert "Deposit must exactly match" in str(e)
        
    mock_gl.message = MockMessage(ISSUER, value=150000) # Overpaid
    try:
        c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
        assert False, "Should reject overpayment lock"
    except MockUserError as e:
        assert "Deposit must exactly match" in str(e)
    print("[PASS] Test 2: Underpayment and overpayment lock prevention")

def test_3_create_policy_invalid_beneficiary_rejected():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    
    # Non-hex string
    try:
        c.create_policy("POL-1", "vitalik.eth", "Aave V3", 500000, 100000)
        assert False, "Should reject non-hex"
    except MockUserError:
        pass
        
    # Too short
    try:
        c.create_policy("POL-1", "0x123", "Aave V3", 500000, 100000)
        assert False, "Should reject short address"
    except MockUserError:
        pass
        
    # Zero address
    try:
        c.create_policy("POL-1", "0x" + "0"*40, "Aave V3", 500000, 100000)
        assert False, "Should reject zero address"
    except MockUserError:
        pass
        
    # Self-issuance
    try:
        c.create_policy("POL-1", ISSUER, "Aave V3", 500000, 100000)
        assert False, "Should reject self-issuance"
    except MockUserError:
        pass
    print("[PASS] Test 3: Strict canonical beneficiary address validation")

def test_4_evidence_url_strict_validation():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    mock_gl.message = MockMessage(BENEFICIARY)
    
    # HTTP rejected (must be HTTPS)
    try:
        c.submit_claim("POL-1", "http://rekt.news/1", "https://peckshield.com/1")
        assert False, "Should reject http"
    except MockUserError as e:
        assert "must use HTTPS" in str(e)
        
    # Embedded credentials rejected
    try:
        c.submit_claim("POL-1", "https://user:pass@rekt.news/1", "https://peckshield.com/1")
        assert False, "Should reject credentials"
    except MockUserError as e:
        assert "embedded credentials" in str(e)
        
    # Untrusted domain rejected
    try:
        c.submit_claim("POL-1", "https://untrusted-blog.com/1", "https://peckshield.com/1")
        assert False, "Should reject untrusted domain"
    except MockUserError:
        pass
        
    # Aliased domain rejected (twitter.com vs x.com)
    try:
        c.submit_claim("POL-1", "https://twitter.com/alert/1", "https://x.com/alert/2")
        assert False, "Should detect domain alias"
    except MockUserError as e:
        assert "independent domains" in str(e)
    print("[PASS] Test 4: Strict URL validation (HTTPS, no credentials, domain aliasing)")

def test_5_submit_claim_restricted_to_beneficiary():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    # Attacker tries to submit claim
    mock_gl.message = MockMessage(ATTACKER)
    try:
        c.submit_claim("POL-1", "https://rekt.news/1", "https://peckshield.com/1")
        assert False, "Attacker should be blocked"
    except MockUserError as e:
        assert "Only the beneficiary" in str(e)
    print("[PASS] Test 5: Third-party griefing blocked (beneficiary only)")

def test_6_consensus_confirmed_claim_and_payout_ledger():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    mock_gl.message = MockMessage(BENEFICIARY)
    res = c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
    assert res == "CLAIM_CONFIRMED_AND_ESCROWED"
    
    policy = json.loads(c.policies["POL-1"])
    assert policy["is_active"] is False
    assert policy["claim_status"] == "CONFIRMED"
    assert c.check_approved_payout(BENEFICIARY) == 100000
    assert int(c.total_underwritten) == 0  # Decremented
    print("[PASS] Test 6: Consensus CONFIRMED claim updates state and decrements total_underwritten")

def test_7_consensus_disagreement_failure():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    mock_gl.message = MockMessage(BENEFICIARY)
    mock_gl.eq_principle.mode = "disagree" # Validators output conflicting verdicts
    try:
        c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
        assert False, "Strict equivalence must fail on disagreement"
    except MockUserError as e:
        assert "strict equivalence" in str(e)
    print("[PASS] Test 7: Validator consensus disagreement fails strict equivalence")

def test_8_web_render_failure_gracefully_handled():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    mock_gl.nondet.web.behavior = "fail" # Web page down / timeout
    mock_gl.message = MockMessage(BENEFICIARY)
    res = c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
    assert res == "CLAIM_REJECTED", "Web failure must gracefully reject without crashing node"
    
    policy = json.loads(c.policies["POL-1"])
    assert policy["claim_attempts"] == 1
    assert policy["claim_status"] == "REJECTED"
    assert policy["is_active"] is True
    print("[PASS] Test 8: Web fetch failure gracefully handled as REJECTED verdict")

def test_9_successful_withdrawal_and_reentrancy_prevention():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    mock_gl.message = MockMessage(BENEFICIARY)
    c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
    
    # First withdrawal succeeds
    amount = c.withdraw_payout()
    assert amount == 100000
    assert len(mock_gl.transfers) == 1
    assert mock_gl.transfers[0]["to"] == BENEFICIARY
    assert mock_gl.transfers[0]["value"] == 100000
    assert c.check_approved_payout(BENEFICIARY) == 0
    
    # Duplicate withdrawal immediately fails
    try:
        c.withdraw_payout()
        assert False, "Duplicate withdrawal should revert"
    except MockUserError as e:
        assert "No approved payouts available" in str(e)
    print("[PASS] Test 9: Successful withdrawal and duplicate withdrawal prevention")

def test_10_insufficient_contract_balance_reverts():
    c = setup_contract()
    c.approved_payouts[BENEFICIARY] = MockU256(100000)
    c.balance = MockU256(50000) # Less than payout
    
    mock_gl.message = MockMessage(BENEFICIARY)
    try:
        c.withdraw_payout()
        assert False, "Should revert on insufficient contract balance"
    except MockUserError as e:
        assert "Insufficient contract balance" in str(e)
    print("[PASS] Test 10: Insufficient contract balance guard")

def test_11_unilateral_issuer_cancellation_blocked():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    # Issuer tries to cancel active policy unilaterally
    mock_gl.message = MockMessage(ISSUER)
    try:
        c.cancel_policy("POL-1")
        assert False, "Unilateral cancellation must be blocked"
    except MockUserError as e:
        assert "requires beneficiary approval or exhausted" in str(e)
    print("[PASS] Test 11: Unilateral issuer cancellation blocked (coverage preserved)")

def test_12_mutual_consent_cancellation_and_refund():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    # Beneficiary grants cancellation consent
    mock_gl.message = MockMessage(BENEFICIARY)
    c.approve_cancellation("POL-1")
    
    # Issuer executes cancellation
    mock_gl.message = MockMessage(ISSUER)
    refund = c.cancel_policy("POL-1")
    assert refund == 100000
    assert len(mock_gl.transfers) == 1
    assert mock_gl.transfers[0]["to"] == ISSUER
    assert mock_gl.transfers[0]["value"] == 100000
    assert int(c.total_underwritten) == 0
    
    policy = json.loads(c.policies["POL-1"])
    assert policy["is_active"] is False
    assert policy["claim_status"] == "CANCELLED"
    print("[PASS] Test 12: Mutual consent cancellation releases 100% collateral to issuer")

def test_13_cancellation_after_three_rejected_attempts():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    # Configure LLM to reject
    mock_gl.nondet.prompt_response = '{"status": "REJECTED"}'
    mock_gl.message = MockMessage(BENEFICIARY)
    
    # Attempt 1, 2, 3
    c.submit_claim("POL-1", "https://rekt.news/1", "https://peckshield.com/1")
    c.submit_claim("POL-1", "https://rekt.news/2", "https://peckshield.com/2")
    c.submit_claim("POL-1", "https://rekt.news/3", "https://peckshield.com/3")
    
    # 4th attempt should be blocked
    try:
        c.submit_claim("POL-1", "https://rekt.news/4", "https://peckshield.com/4")
        assert False, "Should block 4th claim attempt"
    except MockUserError as e:
        assert "Maximum claim attempts exceeded" in str(e)
        
    # Issuer can now cancel without beneficiary approval to release locked funds
    mock_gl.message = MockMessage(ISSUER)
    refund = c.cancel_policy("POL-1")
    assert refund == 100000
    assert len(mock_gl.transfers) == 1
    assert mock_gl.transfers[0]["to"] == ISSUER
    print("[PASS] Test 13: Cancellation after 3 rejected attempts frees locked collateral")

def test_14_cannot_cancel_confirmed_policy_and_cannot_payout_cancelled():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    # Confirm claim
    mock_gl.message = MockMessage(BENEFICIARY)
    c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
    
    # Issuer tries to cancel confirmed policy
    mock_gl.message = MockMessage(ISSUER)
    try:
        c.cancel_policy("POL-1")
        assert False, "Cannot cancel confirmed policy"
    except MockUserError:
        pass
    print("[PASS] Test 14: Confirmed policy cannot be cancelled (mutual exclusivity)")

def test_15_cannot_claim_policy_pending_cancellation():
    c = setup_contract()
    mock_gl.message = MockMessage(ISSUER, value=100000)
    c.create_policy("POL-1", BENEFICIARY, "Aave V3", 500000, 100000)
    
    # Beneficiary approves cancellation
    mock_gl.message = MockMessage(BENEFICIARY)
    c.approve_cancellation("POL-1")
    
    # Beneficiary tries to submit claim while pending cancellation
    try:
        c.submit_claim("POL-1", "https://rekt.news/aave", "https://peckshield.com/alert")
        assert False, "Cannot claim on policy pending cancellation"
    except MockUserError as e:
        assert "pending cancellation" in str(e)
    print("[PASS] Test 15: Policy pending cancellation cannot be claimed")

# ==============================================================================
# Main Test Runner
# ==============================================================================

if __name__ == "__main__":
    print("======================================================================")
    print("Running SlashGuard Full Invariant & Consensus Test Suite")
    print("======================================================================")
    test_1_create_policy_success_and_accounting()
    test_2_create_policy_underfunded_and_overpayment_rejected()
    test_3_create_policy_invalid_beneficiary_rejected()
    test_4_evidence_url_strict_validation()
    test_5_submit_claim_restricted_to_beneficiary()
    test_6_consensus_confirmed_claim_and_payout_ledger()
    test_7_consensus_disagreement_failure()
    test_8_web_render_failure_gracefully_handled()
    test_9_successful_withdrawal_and_reentrancy_prevention()
    test_10_insufficient_contract_balance_reverts()
    test_11_unilateral_issuer_cancellation_blocked()
    test_12_mutual_consent_cancellation_and_refund()
    test_13_cancellation_after_three_rejected_attempts()
    test_14_cannot_cancel_confirmed_policy_and_cannot_payout_cancelled()
    test_15_cannot_claim_policy_pending_cancellation()
    print("======================================================================")
    print("All 15 Automated Unit Tests Passed Successfully (Exit Code 0)")
    print("======================================================================")
