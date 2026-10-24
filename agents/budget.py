"""Spending guard: caps how many real Grok connections one server process may open.

Owner: Person 2 (Grok Agent Intelligence). Every path that spends xAI credits
(investigations, hazard-globe reviews, seasonal watches, weather briefs) builds a
GrokClient, and GrokClient counts one unit per real connection here, so the cap
protects your credits no matter which part of the app is used or who opens it.
Set EARTHWATCH_MAX_INVESTIGATIONS in the deployment's secrets to change the cap
(0 disables it). The count resets when the server restarts.
"""

import logging
import os
import threading

from agents.agent_errors import BudgetExceededError

logger = logging.getLogger(__name__)

ENV_NAME = "EARTHWATCH_MAX_INVESTIGATIONS"
DEFAULT_MAX_INVESTIGATIONS = 60
LIMIT_MESSAGE = (
    "This deployment has reached its limit of {limit} investigations. "
    "Please contact the EarthWatch team to continue."
)


# =============================================================================
# InvestigationBudget
# =============================================================================

# Thread-safe counter of investigations started by this process.
class InvestigationBudget:
    # Creates a budget; a limit of None means unlimited.
    def __init__(self, limit: int | None) -> None:
        self.limit = limit
        self.used = 0
        self._lock = threading.Lock()

    # Reserves one investigation or raises BudgetExceededError when none are left.
    def claim(self) -> None:
        with self._lock:
            if self.limit is not None and self.used >= self.limit:
                raise BudgetExceededError(LIMIT_MESSAGE.format(limit=self.limit))
            self.used += 1

    # Returns how many investigations remain, or None when unlimited.
    @property
    def remaining(self) -> int | None:
        return None if self.limit is None else max(self.limit - self.used, 0)


# Reads the configured cap; invalid values fall back to the safe default.
def read_limit(raw_value: str | None) -> int | None:
    if raw_value is None or not raw_value.strip():
        return DEFAULT_MAX_INVESTIGATIONS
    try:
        limit = int(raw_value.strip())
    except ValueError:
        logger.warning("%s is not an integer; using the default cap.", ENV_NAME)
        return DEFAULT_MAX_INVESTIGATIONS
    if limit < 0:
        logger.warning("%s is negative; using the default cap.", ENV_NAME)
        return DEFAULT_MAX_INVESTIGATIONS
    return None if limit == 0 else limit


_budget: InvestigationBudget | None = None
_budget_lock = threading.Lock()


# Returns the process-wide budget, creating it from the environment on first use.
def get_budget() -> InvestigationBudget:
    global _budget
    with _budget_lock:
        if _budget is None:
            _budget = InvestigationBudget(read_limit(os.getenv(ENV_NAME)))
        return _budget


# Reserves one investigation from the process-wide budget.
def claim_investigation() -> None:
    get_budget().claim()


# Forgets the process-wide budget so the next use re-reads the environment.
def reset_budget() -> None:
    global _budget
    with _budget_lock:
        _budget = None
