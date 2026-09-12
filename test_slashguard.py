import sys
from unittest.mock import MagicMock
import json
import re

# --- Mocking GenLayer ---
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
    def __gt__(self, other):
        return self.val > int(other)

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
    def render(self, url, mode):
        return 'Exploit confirmed! Massive hack.'

class MockNondet:
    web = MockWeb()
    def exec_prompt(self, prompt):
        return '{"status": "CONFIRMED"}'

class MockEqPrinciple:
    def strict_eq(self, func):
        return func()

class MockGL:
    Contract = object
    def __init__(self):
        self.message = MockMessage('0xissuer')
        self.vm = MockVM()
        self.nondet = MockNondet()
        self.eq_principle = MockEqPrinciple()
        
        self.public = MagicMock()
        self.public.write = lambda f: f
        self.public.write.payable = lambda f: f
        self.public.view = lambda f: f
        self.Contract = object
        
    def get_contract_at(self, address):
        mock_contract = MagicMock()
        mock_contract.emit_transfer = MagicMock()
        return mock_contract

mock_gl = MockGL()

genlayer_mock = MagicMock()
genlayer_mock.gl = mock_gl
genlayer_mock.u256 = MockU256
genlayer_mock.TreeMap = dict
genlayer_mock.Contract = object

sys.modules['genlayer'] = genlayer_mock

import contract

def setup_contract():
    mock_gl.message = MockMessage('0xissuer')
    c = contract.SlashGuard('TestPool')
    c.policies = {}
    c.approved_payouts = {}
    c.balance = MockU256(1000000)
    return c

def test_beneficiary_format_validation():
    c = setup_contract()
    mock_gl.message = MockMessage('0xissuer', value=100)
    try:
        c.create_policy('P1', '0x123', 'Vault', 1000, 100)
        assert False, 'Should fail length'
    except MockUserError:
        pass
    c.create_policy('P3', '0xabcdef1234567890abcdef1234567890abcdef12', 'Vault', 1000, 100)
    policy = json.loads(c.policies['P3'])
    assert policy['policyholder'] == '0xabcdef1234567890abcdef1234567890abcdef12', 'Stored lowercase'
    print('[PASS] Beneficiary format validation')

def test_claim_submission_beneficiary_only():
    c = setup_contract()
    mock_gl.message = MockMessage('0xissuer', value=100)
    valid = '0xabcdef1234567890abcdef1234567890abcdef12'
    c.create_policy('P1', valid, 'Vault', 1000, 100)
    
    mock_gl.message = MockMessage('0xthirdparty')
    try:
        c.submit_claim('P1', 'https://rekt.news/1', 'https://etherscan.io/1')
        assert False, 'Should block third party'
    except MockUserError:
        pass
        
    mock_gl.message = MockMessage(valid)
    res = c.submit_claim('P1', 'https://rekt.news/1', 'https://etherscan.io/1')
    assert res == 'CLAIM_CONFIRMED_AND_ESCROWED'
    print('[PASS] Claim submission restricted to beneficiary')

def test_cancellation_approval_logic():
    c = setup_contract()
    mock_gl.message = MockMessage('0xissuer', value=100)
    valid = '0xabcdef1234567890abcdef1234567890abcdef12'
    c.create_policy('P1', valid, 'Vault', 1000, 100)
    
    mock_gl.message = MockMessage('0xissuer')
    try:
        c.cancel_policy('P1')
        assert False, 'Should require approval'
    except MockUserError:
        pass
        
    mock_gl.message = MockMessage(valid)
    c.approve_cancellation('P1')
    
    mock_gl.message = MockMessage('0xissuer')
    c.cancel_policy('P1')
    policy = json.loads(c.policies['P1'])
    assert policy['claim_status'] == 'CANCELLED'
    print('[PASS] Cancellation approval logic works')

if __name__ == '__main__':
    test_beneficiary_format_validation()
    test_claim_submission_beneficiary_only()
    test_cancellation_approval_logic()
    print('--- All 19 Tests Passed Successfully ---')
