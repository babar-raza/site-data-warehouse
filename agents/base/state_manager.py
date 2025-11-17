"""Agent state management with persistence, transitions, and recovery."""

import asyncio
import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class AgentState(Enum):
    """Possible agent states."""
    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    IDLE = "idle"
    ERROR = "error"
    RECOVERING = "recovering"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"


@dataclass
class StateSnapshot:
    """Snapshot of agent state at a point in time."""
    agent_id: str
    state: AgentState
    data: Dict[str, Any]
    timestamp: datetime
    transition_from: Optional[AgentState] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'agent_id': self.agent_id,
            'state': self.state.value,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'transition_from': self.transition_from.value if self.transition_from else None,
            'metadata': self.metadata or {}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateSnapshot':
        """Create from dictionary."""
        return cls(
            agent_id=data['agent_id'],
            state=AgentState(data['state']),
            data=data['data'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            transition_from=AgentState(data['transition_from']) if data.get('transition_from') else None,
            metadata=data.get('metadata', {})
        )


class StateManager:
    """Manages agent state with persistence, transitions, and recovery."""

    # Valid state transitions
    VALID_TRANSITIONS = {
        AgentState.CREATED: [AgentState.INITIALIZING],
        AgentState.INITIALIZING: [AgentState.READY, AgentState.ERROR],
        AgentState.READY: [AgentState.ACTIVE, AgentState.IDLE, AgentState.SHUTTING_DOWN],
        AgentState.ACTIVE: [AgentState.IDLE, AgentState.ERROR, AgentState.SHUTTING_DOWN],
        AgentState.IDLE: [AgentState.ACTIVE, AgentState.SHUTTING_DOWN],
        AgentState.ERROR: [AgentState.RECOVERING, AgentState.TERMINATED],
        AgentState.RECOVERING: [AgentState.READY, AgentState.ERROR],
        AgentState.SHUTTING_DOWN: [AgentState.TERMINATED],
        AgentState.TERMINATED: []
    }

    def __init__(self, storage_path: str = "./data/agent_states"):
        """Initialize state manager.
        
        Args:
            storage_path: Path to store state files
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._states: Dict[str, AgentState] = {}
        self._state_data: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._history: Dict[str, List[StateSnapshot]] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        self._max_history = 100

    async def initialize_agent(self, agent_id: str, initial_data: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize a new agent with state.
        
        Args:
            agent_id: Agent identifier
            initial_data: Initial state data
            
        Returns:
            True if successful
        """
        async with self._locks[agent_id]:
            if agent_id in self._states:
                return False
            
            self._states[agent_id] = AgentState.CREATED
            self._state_data[agent_id] = initial_data or {}
            
            snapshot = StateSnapshot(
                agent_id=agent_id,
                state=AgentState.CREATED,
                data=self._state_data[agent_id].copy(),
                timestamp=datetime.now()
            )
            self._history[agent_id].append(snapshot)
            
            await self._persist_state(agent_id)
            return True

    async def transition(
        self,
        agent_id: str,
        target_state: AgentState,
        state_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Transition agent to a new state.
        
        Args:
            agent_id: Agent identifier
            target_state: Target state to transition to
            state_data: Optional state data to update
            metadata: Optional metadata about the transition
            
        Returns:
            True if transition successful
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        async with self._locks[agent_id]:
            current_state = self._states.get(agent_id)
            if current_state is None:
                raise StateTransitionError(f"Agent {agent_id} not initialized")
            
            # Validate transition
            if target_state not in self.VALID_TRANSITIONS.get(current_state, []):
                raise StateTransitionError(
                    f"Invalid transition from {current_state.value} to {target_state.value}"
                )
            
            # Update state
            self._states[agent_id] = target_state
            
            # Update state data if provided
            if state_data:
                self._state_data[agent_id].update(state_data)
            
            # Record in history
            snapshot = StateSnapshot(
                agent_id=agent_id,
                state=target_state,
                data=self._state_data[agent_id].copy(),
                timestamp=datetime.now(),
                transition_from=current_state,
                metadata=metadata
            )
            self._history[agent_id].append(snapshot)
            
            # Trim history if needed
            if len(self._history[agent_id]) > self._max_history:
                self._history[agent_id] = self._history[agent_id][-self._max_history:]
            
            # Persist
            await self._persist_state(agent_id)
            
            return True

    async def get_state(self, agent_id: str) -> Optional[AgentState]:
        """Get current state of an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Current state or None if not found
        """
        return self._states.get(agent_id)

    async def get_state_data(self, agent_id: str) -> Dict[str, Any]:
        """Get state data for an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            State data dictionary
        """
        return self._state_data.get(agent_id, {}).copy()

    async def update_state_data(self, agent_id: str, data: Dict[str, Any]) -> bool:
        """Update state data without changing state.
        
        Args:
            agent_id: Agent identifier
            data: Data to update
            
        Returns:
            True if successful
        """
        async with self._locks[agent_id]:
            if agent_id not in self._states:
                return False
            
            self._state_data[agent_id].update(data)
            await self._persist_state(agent_id)
            return True

    async def get_history(self, agent_id: str, limit: Optional[int] = None) -> List[StateSnapshot]:
        """Get state history for an agent.
        
        Args:
            agent_id: Agent identifier
            limit: Optional limit on number of snapshots to return
            
        Returns:
            List of state snapshots
        """
        history = self._history.get(agent_id, [])
        if limit:
            return history[-limit:]
        return history.copy()

    async def recover_agent(self, agent_id: str) -> bool:
        """Recover agent state from persistent storage.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if recovery successful
        """
        state_file = self.storage_path / f"{agent_id}.json"
        if not state_file.exists():
            return False
        
        try:
            async with aiofiles.open(state_file, 'r') as f:
                content = await f.read()
                data = json.loads(content)
            
            async with self._locks[agent_id]:
                self._states[agent_id] = AgentState(data['state'])
                self._state_data[agent_id] = data['data']
                
                # Restore history if available
                if 'history' in data:
                    self._history[agent_id] = [
                        StateSnapshot.from_dict(snapshot_dict)
                        for snapshot_dict in data['history']
                    ]
            
            return True
        except Exception as e:
            print(f"Error recovering state for {agent_id}: {e}")
            return False

    async def _persist_state(self, agent_id: str):
        """Persist agent state to disk.
        
        Args:
            agent_id: Agent identifier
        """
        state_file = self.storage_path / f"{agent_id}.json"
        
        data = {
            'agent_id': agent_id,
            'state': self._states[agent_id].value,
            'data': self._state_data[agent_id],
            'last_updated': datetime.now().isoformat(),
            'history': [snapshot.to_dict() for snapshot in self._history[agent_id][-10:]]
        }
        
        try:
            async with aiofiles.open(state_file, 'w') as f:
                await f.write(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Error persisting state for {agent_id}: {e}")

    async def cleanup_agent(self, agent_id: str) -> bool:
        """Remove agent state and cleanup resources.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if successful
        """
        async with self._locks[agent_id]:
            if agent_id in self._states:
                del self._states[agent_id]
            if agent_id in self._state_data:
                del self._state_data[agent_id]
            if agent_id in self._history:
                del self._history[agent_id]
            
            # Remove state file
            state_file = self.storage_path / f"{agent_id}.json"
            if state_file.exists():
                state_file.unlink()
            
            return True

    def get_all_agents(self) -> List[str]:
        """Get list of all agent IDs.
        
        Returns:
            List of agent IDs
        """
        return list(self._states.keys())


async def main():
    """Test state manager."""
    print("Testing State Manager...")
    
    manager = StateManager()
    
    # Test initialization
    agent_id = "test_agent_001"
    await manager.initialize_agent(agent_id, {"counter": 0})
    print(f"✓ Initialized agent {agent_id}")
    
    # Test transitions
    await manager.transition(agent_id, AgentState.INITIALIZING)
    await manager.transition(agent_id, AgentState.READY)
    await manager.transition(agent_id, AgentState.ACTIVE, {"counter": 1})
    print("✓ State transitions successful")
    
    # Test state retrieval
    state = await manager.get_state(agent_id)
    data = await manager.get_state_data(agent_id)
    print(f"✓ Current state: {state.value}, data: {data}")
    
    # Test history
    history = await manager.get_history(agent_id)
    print(f"✓ History has {len(history)} snapshots")
    
    # Test recovery
    await manager.recover_agent(agent_id)
    print("✓ Recovery successful")
    
    # Test invalid transition
    try:
        await manager.transition(agent_id, AgentState.TERMINATED)
        print("✗ Should have failed on invalid transition")
    except StateTransitionError:
        print("✓ Invalid transition properly rejected")
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
