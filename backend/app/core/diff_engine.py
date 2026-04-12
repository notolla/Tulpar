"""
DiffEngine - Delta computation layer
Computes added/updated/removed aircraft for efficient updates
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class StateDiff:
    """Represents difference between two state snapshots"""
    added: List[Dict[str, Any]]
    updated: List[Dict[str, Any]]
    removed: List[str]
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "diff",
            "timestamp": self.timestamp,
            "added": self.added,
            "updated": self.updated,
            "removed": self.removed
        }
    
    def is_empty(self) -> bool:
        """Check if diff contains any changes"""
        return len(self.added) == 0 and len(self.updated) == 0 and len(self.removed) == 0
    
    def size(self) -> int:
        """Total number of changes"""
        return len(self.added) + len(self.updated) + len(self.removed)


class DiffEngine:
    """
    Computes state differences for efficient WebSocket updates
    - Tracks previous state
    - Detects added, updated, removed aircraft
    - Optimizes payload size
    """
    
    def __init__(self):
        self._previous_state: Dict[str, Dict[str, Any]] = {}
        self._last_diff: Optional[StateDiff] = None
        
    def compute_diff(self, current_state: Dict[str, Dict[str, Any]]) -> StateDiff:
        """
        Compute diff between previous and current state
        Returns: StateDiff with added, updated, removed lists
        """
        previous_ids = set(self._previous_state.keys())
        current_ids = set(current_state.keys())
        
        # Find added, removed, potentially updated
        added_ids = current_ids - previous_ids
        removed_ids = previous_ids - current_ids
        common_ids = current_ids & previous_ids
        
        # Build diff lists
        added = []
        updated = []
        removed = list(removed_ids)
        
        # Process added aircraft
        for aircraft_id in added_ids:
            added.append(current_state[aircraft_id])
        
        # Process updated aircraft (only if significant change)
        for aircraft_id in common_ids:
            prev = self._previous_state[aircraft_id]
            curr = current_state[aircraft_id]
            
            if self._has_significant_change(prev, curr):
                updated.append(curr)
        
        # Create diff
        diff = StateDiff(
            added=added,
            updated=updated,
            removed=removed,
            timestamp=datetime.now().isoformat()
        )
        
        # Store current as previous for next comparison
        self._previous_state = current_state.copy()
        self._last_diff = diff
        
        if not diff.is_empty():
            logger.debug(f"Diff computed: {diff.size()} changes ({len(added)} added, {len(updated)} updated, {len(removed)} removed)")
        
        return diff
    
    def _has_significant_change(self, prev: Dict[str, Any], curr: Dict[str, Any]) -> bool:
        """
        Determine if change between prev and curr is significant enough to broadcast
        Thresholds:
        - Position: > 0.001 degrees (~100m)
        - Altitude: > 100 feet
        - Speed: > 10 knots
        - Heading: > 5 degrees
        """
        # Position change threshold (approx 100 meters)
        if abs(prev.get("lat", 0) - curr.get("lat", 0)) > 0.001:
            return True
        if abs(prev.get("lon", 0) - curr.get("lon", 0)) > 0.001:
            return True
        
        # Altitude change > 100 feet
        if abs(prev.get("altitude", 0) - curr.get("altitude", 0)) > 100:
            return True
        
        # Speed change > 10 knots
        if abs(prev.get("speed", 0) - curr.get("speed", 0)) > 10:
            return True
        
        # Heading change > 5 degrees
        if abs(prev.get("heading", 0) - curr.get("heading", 0)) > 5:
            return True
        
        # Anomaly score change
        if prev.get("anomaly_score", 0) != curr.get("anomaly_score", 0):
            return True
        
        return False
    
    def get_full_state(self, current_state: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Get full state as a reset message"""
        return {
            "type": "full",
            "timestamp": datetime.now().isoformat(),
            "aircraft": list(current_state.values())
        }
    
    def get_heartbeat(self) -> Dict[str, Any]:
        """Get heartbeat message"""
        return {
            "type": "heartbeat",
            "timestamp": datetime.now().isoformat(),
            "status": "live"
        }
    
    def reset(self):
        """Reset diff tracking (e.g., for client reconnect)"""
        self._previous_state = {}
        self._last_diff = None
        logger.info("DiffEngine reset")


# Global singleton
diff_engine = DiffEngine()
