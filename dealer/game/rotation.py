from __future__ import annotations

from .models import Agenda, AgendaRound


class AgendaExhausted(RuntimeError):
    pass


class AgendaRotation:
    """Dealer-only cursor over one fixed, pre-registered agenda."""

    def __init__(self, agenda: Agenda, season_rounds: int):
        if season_rounds <= 0:
            raise ValueError("season_rounds must be positive")
        if season_rounds > len(agenda.rounds):
            raise ValueError("season_rounds exceeds the selected agenda")
        self._rounds = agenda.rounds[:season_rounds]
        self._cursor = 0

    @property
    def consumed(self) -> int:
        return self._cursor

    @property
    def remaining(self) -> int:
        return len(self._rounds) - self._cursor

    def next(self) -> AgendaRound:
        if self._cursor >= len(self._rounds):
            raise AgendaExhausted("selected agenda is complete")
        selected = self._rounds[self._cursor]
        self._cursor += 1
        return selected
