"""
Odds data model.

Represents betting odds for a dog in a race from a specific bookmaker at a point in time.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any


@dataclass
class Odds:
    """
    Betting odds entity.
    
    Attributes:
        odds_id: Unique identifier for this odds snapshot
        race_id: Foreign key to the race
        dog_id: Foreign key to the dog
        bookmaker: Name of the bookmaker providing these odds
        decimal_odds: Odds in decimal format (e.g., 3.50)
        fractional_odds: Odds in fractional format (e.g., "5/2")
        timestamp: When these odds were scraped from oddschecker
        created_at: Timestamp when record was created
    """
    odds_id: str
    race_id: str
    dog_id: str
    bookmaker: str
    decimal_odds: float
    fractional_odds: str
    timestamp: datetime
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Odds instance to dictionary for serialization.
        
        Returns:
            Dictionary representation with datetime objects as ISO strings
        """
        return {
            'odds_id': self.odds_id,
            'race_id': self.race_id,
            'dog_id': self.dog_id,
            'bookmaker': self.bookmaker,
            'decimal_odds': self.decimal_odds,
            'fractional_odds': self.fractional_odds,
            'timestamp': self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Odds':
        """
        Create Odds instance from dictionary.
        
        Args:
            data: Dictionary containing odds data
            
        Returns:
            Odds instance
        """
        # Convert ISO string timestamps back to datetime objects
        timestamp = data['timestamp']
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
            
        created_at = data.get('created_at', datetime.now())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        return cls(
            odds_id=data['odds_id'],
            race_id=data['race_id'],
            dog_id=data['dog_id'],
            bookmaker=data['bookmaker'],
            decimal_odds=data['decimal_odds'],
            fractional_odds=data['fractional_odds'],
            timestamp=timestamp,
            created_at=created_at,
        )
