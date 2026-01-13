"""
Race data model.

Represents a greyhound race with timing, location, and status information.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any


@dataclass
class Race:
    """
    Greyhound race entity.
    
    Attributes:
        race_id: Unique identifier for the race
        track_name: Name of the racing track
        race_time: Scheduled time for the race
        distance: Race distance in meters
        status: Current race status (scheduled/in_progress/completed)
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """
    race_id: str
    track_name: str
    race_time: datetime
    distance: int
    status: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert Race instance to dictionary for serialization.
        
        Returns:
            Dictionary representation with datetime objects as ISO strings
        """
        return {
            'race_id': self.race_id,
            'track_name': self.track_name,
            'race_time': self.race_time.isoformat() if isinstance(self.race_time, datetime) else self.race_time,
            'distance': self.distance,
            'status': self.status,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'updated_at': self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Race':
        """
        Create Race instance from dictionary.
        
        Args:
            data: Dictionary containing race data
            
        Returns:
            Race instance
        """
        # Convert ISO string timestamps back to datetime objects
        race_time = data['race_time']
        if isinstance(race_time, str):
            race_time = datetime.fromisoformat(race_time)
            
        created_at = data.get('created_at', datetime.now())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
            
        updated_at = data.get('updated_at', datetime.now())
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        
        return cls(
            race_id=data['race_id'],
            track_name=data['track_name'],
            race_time=race_time,
            distance=data['distance'],
            status=data['status'],
            created_at=created_at,
            updated_at=updated_at,
        )
