"""Agent registry for discovery, registration, health monitoring, and failover."""

import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiofiles

from agents.base.agent_contract import AgentHealth, AgentMetadata, AgentStatus


@dataclass
class AgentRegistration:
    """Agent registration information."""
    agent_id: str
    agent_type: str
    metadata: AgentMetadata
    registered_at: datetime
    last_heartbeat: datetime
    health: Optional[AgentHealth] = None
    tags: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        metadata_dict = asdict(self.metadata)
        # Convert datetime objects in metadata
        metadata_dict['created_at'] = self.metadata.created_at.isoformat()
        metadata_dict['updated_at'] = self.metadata.updated_at.isoformat()
        
        health_dict = None
        if self.health:
            health_dict = asdict(self.health)
            health_dict['last_heartbeat'] = self.health.last_heartbeat.isoformat()
            health_dict['status'] = self.health.status.value
        
        return {
            'agent_id': self.agent_id,
            'agent_type': self.agent_type,
            'metadata': metadata_dict,
            'registered_at': self.registered_at.isoformat(),
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'health': health_dict,
            'tags': self.tags or {}
        }


class AgentRegistry:
    """Registry for agent discovery, health monitoring, and load balancing."""

    def __init__(
        self,
        heartbeat_timeout_seconds: int = 30,
        health_check_interval_seconds: int = 10,
        persistence_path: str = "./data/registry"
    ):
        """Initialize agent registry.
        
        Args:
            heartbeat_timeout_seconds: Seconds before agent considered dead
            health_check_interval_seconds: Interval for health checks
            persistence_path: Path to store registry data
        """
        self.heartbeat_timeout = timedelta(seconds=heartbeat_timeout_seconds)
        self.health_check_interval = health_check_interval_seconds
        self.persistence_path = Path(persistence_path)
        self.persistence_path.mkdir(parents=True, exist_ok=True)
        
        self._agents: Dict[str, AgentRegistration] = {}
        self._agents_by_type: Dict[str, Set[str]] = defaultdict(set)
        self._agent_capabilities: Dict[str, Set[str]] = defaultdict(set)
        
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None
        
        self._stats = {
            'total_registered': 0,
            'active_agents': 0,
            'failed_agents': 0,
            'health_checks': 0
        }

    async def start(self):
        """Start registry background tasks."""
        if self._running:
            return
        
        self._running = True
        
        # Load persisted registry
        await self._load_registry()
        
        # Start health check task
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop(self):
        """Stop registry background tasks."""
        self._running = False
        
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

    async def register(
        self,
        agent_id: str,
        agent_type: str,
        metadata: AgentMetadata,
        tags: Optional[Dict[str, str]] = None
    ) -> bool:
        """Register a new agent.
        
        Args:
            agent_id: Unique agent identifier
            agent_type: Type of agent
            metadata: Agent metadata
            tags: Optional tags for filtering
            
        Returns:
            True if registration successful
        """
        if agent_id in self._agents:
            # Update existing registration
            registration = self._agents[agent_id]
            registration.metadata = metadata
            registration.last_heartbeat = datetime.now()
            if tags:
                registration.tags = tags
        else:
            # New registration
            registration = AgentRegistration(
                agent_id=agent_id,
                agent_type=agent_type,
                metadata=metadata,
                registered_at=datetime.now(),
                last_heartbeat=datetime.now(),
                tags=tags
            )
            self._agents[agent_id] = registration
            self._stats['total_registered'] += 1
        
        # Update indices
        self._agents_by_type[agent_type].add(agent_id)
        
        for capability in metadata.capabilities:
            self._agent_capabilities[capability].add(agent_id)
        
        # Persist
        await self._persist_registration(registration)
        
        return True

    async def unregister(self, agent_id: str) -> bool:
        """Unregister an agent.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if successful
        """
        if agent_id not in self._agents:
            return False
        
        registration = self._agents[agent_id]
        
        # Remove from indices
        self._agents_by_type[registration.agent_type].discard(agent_id)
        
        for capability in registration.metadata.capabilities:
            self._agent_capabilities[capability].discard(agent_id)
        
        # Remove registration
        del self._agents[agent_id]
        
        # Remove persisted data
        reg_file = self.persistence_path / f"{agent_id}.json"
        if reg_file.exists():
            reg_file.unlink()
        
        return True

    async def heartbeat(self, agent_id: str, health: Optional[AgentHealth] = None) -> bool:
        """Record agent heartbeat.
        
        Args:
            agent_id: Agent identifier
            health: Optional health information
            
        Returns:
            True if successful
        """
        if agent_id not in self._agents:
            return False
        
        registration = self._agents[agent_id]
        registration.last_heartbeat = datetime.now()
        
        if health:
            registration.health = health
        
        return True

    async def discover(
        self,
        agent_type: Optional[str] = None,
        capability: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        status: Optional[AgentStatus] = None
    ) -> List[AgentRegistration]:
        """Discover agents matching criteria.
        
        Args:
            agent_type: Filter by agent type
            capability: Filter by capability
            tags: Filter by tags
            status: Filter by status
            
        Returns:
            List of matching agent registrations
        """
        candidates = set(self._agents.keys())
        
        # Filter by type
        if agent_type:
            candidates &= self._agents_by_type.get(agent_type, set())
        
        # Filter by capability
        if capability:
            candidates &= self._agent_capabilities.get(capability, set())
        
        # Get registrations
        registrations = [self._agents[aid] for aid in candidates if aid in self._agents]
        
        # Filter by tags
        if tags:
            registrations = [
                reg for reg in registrations
                if reg.tags and all(
                    reg.tags.get(k) == v for k, v in tags.items()
                )
            ]
        
        # Filter by status
        if status:
            registrations = [
                reg for reg in registrations
                if reg.health and reg.health.status == status
            ]
        
        # Filter out dead agents
        now = datetime.now()
        registrations = [
            reg for reg in registrations
            if (now - reg.last_heartbeat) < self.heartbeat_timeout
        ]
        
        return registrations

    async def get_agent(self, agent_id: str) -> Optional[AgentRegistration]:
        """Get agent registration by ID.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent registration or None
        """
        return self._agents.get(agent_id)

    async def select_agent(
        self,
        agent_type: Optional[str] = None,
        capability: Optional[str] = None,
        load_balance: bool = True
    ) -> Optional[str]:
        """Select an agent for task assignment.
        
        Uses load balancing to select least loaded agent.
        
        Args:
            agent_type: Filter by agent type
            capability: Filter by capability
            load_balance: Whether to use load balancing
            
        Returns:
            Agent ID or None if no suitable agent found
        """
        candidates = await self.discover(
            agent_type=agent_type,
            capability=capability,
            status=AgentStatus.IDLE
        )
        
        if not candidates:
            # Try RUNNING agents if no IDLE agents
            candidates = await self.discover(
                agent_type=agent_type,
                capability=capability,
                status=AgentStatus.RUNNING
            )
        
        if not candidates:
            return None
        
        if load_balance and len(candidates) > 1:
            # Select agent with lowest processed count
            candidates.sort(
                key=lambda r: r.health.processed_count if r.health else float('inf')
            )
        
        return candidates[0].agent_id

    async def get_failover_agent(self, failed_agent_id: str) -> Optional[str]:
        """Get a failover agent to replace a failed agent.
        
        Args:
            failed_agent_id: ID of failed agent
            
        Returns:
            Failover agent ID or None
        """
        if failed_agent_id not in self._agents:
            return None
        
        failed_registration = self._agents[failed_agent_id]
        
        # Find agent of same type with matching capabilities
        candidates = await self.discover(
            agent_type=failed_registration.agent_type,
            status=AgentStatus.IDLE
        )
        
        # Filter by capabilities
        required_capabilities = set(failed_registration.metadata.capabilities)
        candidates = [
            reg for reg in candidates
            if required_capabilities.issubset(set(reg.metadata.capabilities))
            and reg.agent_id != failed_agent_id
        ]
        
        if not candidates:
            return None
        
        # Return agent with lowest load
        candidates.sort(
            key=lambda r: r.health.processed_count if r.health else 0
        )
        
        return candidates[0].agent_id

    async def _health_check_loop(self):
        """Periodic health check loop."""
        while self._running:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                now = datetime.now()
                active_count = 0
                failed_count = 0
                
                for agent_id, registration in list(self._agents.items()):
                    time_since_heartbeat = now - registration.last_heartbeat
                    
                    if time_since_heartbeat > self.heartbeat_timeout:
                        # Agent is dead
                        failed_count += 1
                        
                        # Mark as failed if health exists
                        if registration.health:
                            registration.health.status = AgentStatus.ERROR
                    else:
                        active_count += 1
                
                self._stats['active_agents'] = active_count
                self._stats['failed_agents'] = failed_count
                self._stats['health_checks'] += 1
                
            except Exception as e:
                print(f"Error in health check loop: {e}")

    async def _persist_registration(self, registration: AgentRegistration):
        """Persist agent registration.
        
        Args:
            registration: Registration to persist
        """
        reg_file = self.persistence_path / f"{registration.agent_id}.json"
        
        try:
            async with aiofiles.open(reg_file, 'w') as f:
                await f.write(json.dumps(registration.to_dict(), indent=2))
        except Exception as e:
            print(f"Error persisting registration for {registration.agent_id}: {e}")

    async def _load_registry(self):
        """Load registry from persistence."""
        for reg_file in self.persistence_path.glob("*.json"):
            try:
                async with aiofiles.open(reg_file, 'r') as f:
                    content = await f.read()
                    data = json.loads(content)
                
                # Reconstruct registration
                metadata = AgentMetadata(**data['metadata'])
                health = AgentHealth(**data['health']) if data.get('health') else None
                
                registration = AgentRegistration(
                    agent_id=data['agent_id'],
                    agent_type=data['agent_type'],
                    metadata=metadata,
                    registered_at=datetime.fromisoformat(data['registered_at']),
                    last_heartbeat=datetime.fromisoformat(data['last_heartbeat']),
                    health=health,
                    tags=data.get('tags')
                )
                
                self._agents[registration.agent_id] = registration
                self._agents_by_type[registration.agent_type].add(registration.agent_id)
                
                for capability in metadata.capabilities:
                    self._agent_capabilities[capability].add(registration.agent_id)
                
            except Exception as e:
                print(f"Error loading registration from {reg_file}: {e}")

    def get_stats(self) -> Dict[str, int]:
        """Get registry statistics.
        
        Returns:
            Statistics dictionary
        """
        return self._stats.copy()

    def list_agents(self) -> List[str]:
        """List all registered agent IDs.
        
        Returns:
            List of agent IDs
        """
        return list(self._agents.keys())


async def main():
    """Test agent registry."""
    import sys
    
    parser = argparse.ArgumentParser(description='Agent Registry')
    parser.add_argument('--register', help='Register test agent')
    args = parser.parse_args()
    
    if args.register:
        print(f"Registering test agent: {args.register}")
        
        registry = AgentRegistry()
        await registry.start()
        
        metadata = AgentMetadata(
            agent_id=args.register,
            agent_type="test",
            version="1.0.0",
            capabilities=["test", "demo"],
            dependencies=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        success = await registry.register(args.register, "test", metadata)
        if success:
            print(f"✓ Registered agent {args.register}")
        else:
            print(f"✗ Failed to register agent {args.register}")
        
        await registry.stop()
        return
    
    # Run tests
    print("Testing Agent Registry...")
    
    registry = AgentRegistry(heartbeat_timeout_seconds=5)
    await registry.start()
    print("✓ Registry started")
    
    # Register agents
    for i in range(3):
        agent_id = f"test_agent_{i:03d}"
        metadata = AgentMetadata(
            agent_id=agent_id,
            agent_type="worker",
            version="1.0.0",
            capabilities=["process", "analyze"],
            dependencies=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        await registry.register(agent_id, "worker", metadata)
        
        # Send heartbeat with health
        health = AgentHealth(
            agent_id=agent_id,
            status=AgentStatus.IDLE if i % 2 == 0 else AgentStatus.RUNNING,
            uptime_seconds=100.0,
            last_heartbeat=datetime.now(),
            error_count=0,
            processed_count=i * 10,
            memory_usage_mb=100.0,
            cpu_percent=10.0,
            metadata={}
        )
        await registry.heartbeat(agent_id, health)
    
    print("✓ Registered 3 agents")
    
    # Discovery
    agents = await registry.discover(agent_type="worker")
    print(f"✓ Discovered {len(agents)} worker agents")
    
    agents = await registry.discover(capability="process")
    print(f"✓ Discovered {len(agents)} agents with 'process' capability")
    
    # Selection
    selected = await registry.select_agent(agent_type="worker", capability="analyze")
    print(f"✓ Selected agent for task: {selected}")
    
    # Failover
    failover = await registry.get_failover_agent("test_agent_000")
    print(f"✓ Failover agent: {failover}")
    
    # Stats
    stats = registry.get_stats()
    print(f"✓ Stats: {stats}")
    
    await registry.stop()
    print("✓ Registry stopped")
    
    print("\nAll tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
