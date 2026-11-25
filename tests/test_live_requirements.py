"""
Live integration test: does ReviewerAgent actually judge code against the
ORIGINAL REQUIREMENT, not just generic code quality?

test_plugin_server.py::test_reviewer_and_debugger_receive_the_requirements only
proves the requirements string is threaded through to reviewer.review()/
debugger.fix() — it mocks the agents, so it can't prove the model's judgment
catches a requirement mismatch. This file makes real Claude API calls to prove
that, and costs real API usage, so it's skipped unless a real ANTHROPIC_API_KEY
is configured.
"""
import os
import pytest

# Several sibling test files do os.environ.setdefault("ANTHROPIC_API_KEY",
# "test-key-for-unit-tests") for isolation from needing a real key. Because
# pytest imports test modules in file order, that dummy value can already be
# in os.environ by the time this module is collected — so "is the var set at
# all" is not a reliable presence check here. Explicitly excluding the known
# dummy sentinel is what makes this skip correctly in the normal fast suite.
_DUMMY_KEY = "test-key-for-unit-tests"
_key = os.getenv("ANTHROPIC_API_KEY")
HAS_REAL_KEY = bool(_key) and _key != _DUMMY_KEY

pytestmark = pytest.mark.skipif(
    not HAS_REAL_KEY,
    reason="Needs a real ANTHROPIC_API_KEY in .env — makes live Claude API calls.",
)

from codeagent_mcp.specialized import ReviewerAgent  # noqa: E402  (after the skip check)

SUM_REQUIREMENT = "Write a function sum_list(nums) that returns the sum of a list of numbers."

CORRECT_SUM_CODE = """
def sum_list(nums):
    total = 0
    for n in nums:
        total += n
    return total
"""

WRONG_BEHAVIOR_CODE = """
def sum_list(nums):
    total = 1
    for n in nums:
        total *= n
    return total
"""

AVERAGE_REQUIREMENT = "Write a function average(nums) that returns the average of a list of numbers."

CRASHES_ON_EMPTY_CODE = """
def average(nums):
    return sum(nums) / len(nums)
"""


def test_correct_code_passes():
    review = ReviewerAgent().review(CORRECT_SUM_CODE, SUM_REQUIREMENT)
    print(f"\n[correct code] verdict={'PASS' if review.passed else 'FAIL'} issues={review.issues}")
    assert review.passed, f"Expected PASS, got FAIL with issues: {review.issues}"


def test_wrong_behavior_fails_and_names_the_mismatch():
    review = ReviewerAgent().review(WRONG_BEHAVIOR_CODE, SUM_REQUIREMENT)
    print(f"\n[wrong behavior] verdict={'PASS' if review.passed else 'FAIL'} issues={review.issues}")
    assert not review.passed, "Code computes a product, not a sum — should FAIL."
    issues_text = " ".join(review.issues).lower()
    assert any(word in issues_text for word in ("sum", "product", "multipl", "add")), (
        f"Expected issues to mention the sum/product mismatch, got: {review.issues}"
    )


def test_latent_bug_on_loosely_stated_requirement():
    review = ReviewerAgent().review(CRASHES_ON_EMPTY_CODE, AVERAGE_REQUIREMENT)
    print(f"\n[latent bug] verdict={'PASS' if review.passed else 'FAIL'} issues={review.issues}")
    issues_text = " ".join(review.issues).lower()
    caught = any(word in issues_text for word in ("empty", "zero", "zerodivision", "division"))
    # Real finding either way is useful; don't force a pass if the model doesn't catch it.
    assert caught, (
        f"Model did not flag the empty-list/division-by-zero bug. "
        f"verdict={'PASS' if review.passed else 'FAIL'} issues={review.issues}"
    )
