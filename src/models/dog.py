"""
Dog data model.

Represents a greyhound participating in a race with statistics and trap assignment.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class Dog:
    """
    Greyhound entity.
    
    Attributes:
        dog_id: Unique identifier for the dog
        name: Dog's registered name
        race_id: Foreign key to the race this dog is participating in
        trap_number: Starting trap position (1-6)
        stats: JSON dictionary containing statistics (win_rate, recent_form, track_preference, etc.)
        last_stats_update: Timestamp when statistics were last refreshed
        created_at: Timestamp when record was created
    """
    dog_id: str
    name: str
    race_id: str
    trap_number: int
    stats: Dict[str, Any] = field(default_factory=dict)
    last_stats_update: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate trap number is within valid range."""
        if not 1 <= self.trap_number <= 6:
            raise ValueError(f"Trap number must be between 1 and 6, got {self.trap_number}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Dog instance to dictionary for serialization.
        
        Returns:
            Dictionary representation with datetime objects as ISO strings
        """
        return {
            'dog_id': self.dog_id,
            'name': self.name,
            'race_id': self.race_id,
            'trap_number': self.trap_number,
            'stats': self.stats,
            'last_stats_update': self.last_stats_update.isoformat() if self.last_stats_update else None,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dog':
        """
        Create Dog instance from dictionary.
        
        Args:
            data: Dictionary containing dog data
            
        Returns:
            Dog instance
        """
        # Convert ISO string timestamps back to datetime objects
        last_stats_update = data.get('last_stats_update')
        if isinstance(last_stats_update, str):
            last_stats_update = datetime.fromisoformat(last_stats_update)
            
        created_at = data.get('created_at', datetime.now())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        return cls(
            dog_id=data['dog_id'],
            name=data['name'],
            race_id=data['race_id'],
            trap_number=data['trap_number'],
            stats=data.get('stats', {}),
            last_stats_update=last_stats_update,
            created_at=created_at,
        )
