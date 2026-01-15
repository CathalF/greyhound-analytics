"""
Result and BetRecord data models.

Represents race outcomes and betting history for tracking performance.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional


@dataclass
class Result:
    """
    Race result entity.

    Attributes:
        result_id: Unique identifier (format: {race_id}_{position})
        race_id: Foreign key to the race
        dog_id: Foreign key to the dog
        position: Finishing position (1-6, 1=winner)
        finishing_time: Time in seconds (e.g., "29.45")
        starting_price: SP odds at race start
        created_at: Timestamp when record was created
    """
    result_id: str
    race_id: str
    dog_id: str
    position: int
    finishing_time: Optional[str] = None
    starting_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Result instance to dictionary for serialization.

        Returns:
            Dictionary representation with datetime objects as ISO strings
        """
        return {
            'result_id': self.result_id,
            'race_id': self.race_id,
            'dog_id': self.dog_id,
            'position': self.position,
            'finishing_time': self.finishing_time,
            'starting_price': self.starting_price,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Result':
        """
        Create Result instance from dictionary.

        Args:
            data: Dictionary containing result data

        Returns:
            Result instance
        """
        created_at = data.get('created_at', datetime.now())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return cls(
            result_id=data['result_id'],
            race_id=data['race_id'],
            dog_id=data['dog_id'],
            position=data['position'],
            finishing_time=data.get('finishing_time'),
            starting_price=data.get('starting_price'),
            created_at=created_at,
        )


@dataclass
class BetRecord:
    """
    Bet history entity for tracking value bet suggestions and outcomes.

    Attributes:
        bet_id: Unique identifier (format: {race_id}_{dog_id}_{timestamp})
        race_id: Foreign key to the race
        dog_id: Foreign key to the dog
        suggested_at: When value bet was identified
        value_score: Score at time of suggestion
        best_odds: Best odds when suggested
        best_bookmaker: Bookmaker offering best odds
        outcome: Bet result (pending/won/lost)
        actual_position: Final position after race
        profit_loss: Calculated profit/loss (-1 for lost, odds-1 for won)
        created_at: Timestamp when record was created
    """
    bet_id: str
    race_id: str
    dog_id: str
    suggested_at: datetime
    value_score: float
    best_odds: float
    best_bookmaker: str
    outcome: str = 'pending'
    actual_position: Optional[int] = None
    profit_loss: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert BetRecord instance to dictionary for serialization.

        Returns:
            Dictionary representation with datetime objects as ISO strings
        """
        return {
            'bet_id': self.bet_id,
            'race_id': self.race_id,
            'dog_id': self.dog_id,
            'suggested_at': self.suggested_at.isoformat() if isinstance(self.suggested_at, datetime) else self.suggested_at,
            'value_score': self.value_score,
            'best_odds': self.best_odds,
            'best_bookmaker': self.best_bookmaker,
            'outcome': self.outcome,
            'actual_position': self.actual_position,
            'profit_loss': self.profit_loss,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BetRecord':
        """
        Create BetRecord instance from dictionary.

        Args:
            data: Dictionary containing bet record data

        Returns:
            BetRecord instance
        """
        suggested_at = data['suggested_at']
        if isinstance(suggested_at, str):
            suggested_at = datetime.fromisoformat(suggested_at)

        created_at = data.get('created_at', datetime.now())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return cls(
            bet_id=data['bet_id'],
            race_id=data['race_id'],
            dog_id=data['dog_id'],
            suggested_at=suggested_at,
            value_score=data['value_score'],
            best_odds=data['best_odds'],
            best_bookmaker=data['best_bookmaker'],
            outcome=data.get('outcome', 'pending'),
            actual_position=data.get('actual_position'),
            profit_loss=data.get('profit_loss'),
            created_at=created_at,
        )
