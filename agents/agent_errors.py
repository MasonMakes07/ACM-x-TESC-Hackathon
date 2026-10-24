"""Errors raised inside the agent workflow.

Owner: Person 2 (Grok Agent Intelligence).
"""


# =============================================================================
# GrokError
# =============================================================================

# Raised when the Grok API cannot be reached or returns an unusable response.
class GrokError(Exception):
    pass


# =============================================================================
# AgentOutputError
# =============================================================================

# Raised when an agent cannot produce valid structured output after one repair.
class AgentOutputError(Exception):
    pass


# =============================================================================
# BudgetExceededError
# =============================================================================

# Raised when the deployment's investigation limit has been reached (safe to show).
class BudgetExceededError(Exception):
    pass
