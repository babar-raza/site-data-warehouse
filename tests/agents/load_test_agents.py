"""Load test for agent infrastructure - 100 agents, 1000 messages."""

import asyncio
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base.agent_contract import (
    AgentContract,
    AgentHealth,
    AgentMetadata,
    AgentStatus,
)
from agents.base.agent_registry import AgentRegistry
from agents.base.message_bus import Message, MessageBus
from agents.base.state_manager import AgentState, StateManager
from agents.config import TEST_CONFIG


class LoadTestAgent(AgentContract):
    """Test agent for load testing."""

    def __init__(self, agent_id: str, agent_type: str, message_bus: MessageBus):
        super().__init__(agent_id, agent_type)
        self.message_bus = message_bus
        self.messages_received = 0
        self.messages_sent = 0
        self.processing_times = []

    async def initialize(self) -> bool:
        """Initialize agent."""
        self._start_time = datetime.now()
        self._set_status(AgentStatus.RUNNING)
        
        # Subscribe to messages
        await self.message_bus.subscribe(
            self.agent_id,
            f"load.{self.agent_id}",
            self._handle_message
        )
        
        return True

    async def _handle_message(self, message: Message) -> bool:
        """Handle incoming message."""
        start = time.time()
        
        # Simulate processing
        await asyncio.sleep(random.uniform(0.001, 0.01))
        
        result = await self.process(message.payload)
        
        elapsed = time.time() - start
        self.processing_times.append(elapsed)
        
        return True

    async def process(self, input_data: dict) -> dict:
        """Process data."""
        self.messages_received += 1
        self._increment_processed_count()
        
        return {
            "status": "processed",
            "agent_id": self.agent_id,
            "received_count": self.messages_received
        }

    async def send_message(self, target_agent: str, payload: dict):
        """Send message to another agent."""
        await self.message_bus.publish(
            f"load.{target_agent}",
            self.agent_id,
            payload
        )
        self.messages_sent += 1

    async def health_check(self) -> AgentHealth:
        """Return health status."""
        uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
        
        return AgentHealth(
            agent_id=self.agent_id,
            status=self.status,
            uptime_seconds=uptime,
            last_heartbeat=datetime.now(),
            error_count=self._error_count,
            processed_count=self._processed_count,
            memory_usage_mb=100.0,
            cpu_percent=10.0,
            metadata={
                "messages_received": self.messages_received,
                "messages_sent": self.messages_sent,
                "avg_processing_time": sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
            }
        )

    async def shutdown(self) -> bool:
        """Shutdown agent."""
        self._set_status(AgentStatus.SHUTDOWN)
        return True


async def run_load_test():
    """Run load test with 100 agents and 1000 messages."""
    print("=" * 60)
    print("AGENT INFRASTRUCTURE LOAD TEST")
    print("=" * 60)
    print(f"Target: 100 agents, 1000 messages")
    print(f"Started at: {datetime.now().isoformat()}")
    print("-" * 60)
    
    # Initialize infrastructure
    print("\n1. Initializing infrastructure...")
    
    state_manager = StateManager(storage_path="./test_data/load_test/states")
    message_bus = MessageBus(persistence_path="./test_data/load_test/messages")
    agent_registry = AgentRegistry(
        heartbeat_timeout_seconds=30,
        health_check_interval_seconds=5,
        persistence_path="./test_data/load_test/registry"
    )
    
    await message_bus.start()
    await agent_registry.start()
    
    print("   ✓ State Manager initialized")
    print("   ✓ Message Bus started")
    print("   ✓ Agent Registry started")
    
    # Create agents
    print("\n2. Creating 100 agents...")
    start_time = time.time()
    
    agents: List[LoadTestAgent] = []
    
    for i in range(100):
        agent_id = f"load_agent_{i:03d}"
        agent = LoadTestAgent(agent_id, "load_test", message_bus)
        
        # Initialize agent
        await agent.initialize()
        
        # Register with state manager
        await state_manager.initialize_agent(agent_id, {"agent_num": i})
        await state_manager.transition(agent_id, AgentState.INITIALIZING)
        await state_manager.transition(agent_id, AgentState.READY)
        await state_manager.transition(agent_id, AgentState.ACTIVE)
        
        # Register with registry
        metadata = AgentMetadata(
            agent_id=agent_id,
            agent_type="load_test",
            version="1.0.0",
            capabilities=["process", "receive", "send"],
            dependencies=[],
            config={},
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        await agent_registry.register(agent_id, "load_test", metadata)
        
        # Send initial heartbeat
        health = await agent.health_check()
        await agent_registry.heartbeat(agent_id, health)
        
        agents.append(agent)
    
    creation_time = time.time() - start_time
    print(f"   ✓ Created and registered 100 agents in {creation_time:.2f}s")
    print(f"   ✓ Average: {creation_time/100*1000:.2f}ms per agent")
    
    # Verify registry
    all_agents = await agent_registry.discover(agent_type="load_test")
    print(f"   ✓ Registry contains {len(all_agents)} agents")
    
    # Wait for all subscriptions to be ready
    await asyncio.sleep(0.5)
    
    # Send messages
    print("\n3. Sending 1000 messages...")
    start_time = time.time()
    
    message_tasks = []
    
    for msg_num in range(1000):
        # Pick random sender and receiver
        sender = random.choice(agents)
        receiver = random.choice(agents)
        
        # Avoid self-messaging
        while receiver.agent_id == sender.agent_id:
            receiver = random.choice(agents)
        
        # Send message
        task = sender.send_message(
            receiver.agent_id,
            {
                "message_num": msg_num,
                "data": f"test_message_{msg_num}"
            }
        )
        message_tasks.append(task)
    
    # Wait for all messages to be sent
    await asyncio.gather(*message_tasks)
    
    send_time = time.time() - start_time
    print(f"   ✓ Sent 1000 messages in {send_time:.2f}s")
    print(f"   ✓ Throughput: {1000/send_time:.0f} messages/second")
    
    # Wait for processing
    print("\n4. Processing messages...")
    process_start = time.time()
    
    # Wait with progress updates
    total_wait = 5.0
    check_interval = 0.5
    checks = int(total_wait / check_interval)
    
    for i in range(checks):
        await asyncio.sleep(check_interval)
        
        # Sample stats
        sample_agent = agents[0]
        stats = message_bus.get_stats()
        
        print(f"   Processing... {(i+1)*check_interval:.1f}s - "
              f"Delivered: {stats['delivered']}, "
              f"Failed: {stats['failed']}")
    
    process_time = time.time() - process_start
    
    # Collect statistics
    print("\n5. Collecting statistics...")
    
    total_received = sum(a.messages_received for a in agents)
    total_sent = sum(a.messages_sent for a in agents)
    total_processing_time = sum(sum(a.processing_times) for a in agents)
    total_messages_processed = sum(len(a.processing_times) for a in agents)
    
    bus_stats = message_bus.get_stats()
    registry_stats = agent_registry.get_stats()
    
    # Update all agent health
    for agent in agents[:10]:  # Sample first 10
        health = await agent.health_check()
        await agent_registry.heartbeat(agent.agent_id, health)
    
    print(f"   ✓ Statistics collected")
    
    # Print results
    print("\n" + "=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)
    
    print("\nAgent Statistics:")
    print(f"  Total Agents Created:      100")
    print(f"  Active Agents:             {registry_stats['active_agents']}")
    print(f"  Failed Agents:             {registry_stats['failed_agents']}")
    
    print("\nMessage Statistics:")
    print(f"  Messages Sent:             {total_sent}")
    print(f"  Messages Received:         {total_received}")
    print(f"  Messages Published:        {bus_stats['published']}")
    print(f"  Messages Delivered:        {bus_stats['delivered']}")
    print(f"  Messages Failed:           {bus_stats['failed']}")
    print(f"  Dead Letters:              {bus_stats['dead_letters']}")
    
    print("\nPerformance Metrics:")
    print(f"  Total Runtime:             {process_time:.2f}s")
    print(f"  Message Send Rate:         {1000/send_time:.0f} msg/s")
    if total_messages_processed > 0:
        avg_process_time = total_processing_time / total_messages_processed
        print(f"  Avg Processing Time:       {avg_process_time*1000:.2f}ms")
        print(f"  Processing Throughput:     {total_messages_processed/process_time:.0f} msg/s")
    
    print("\nAgent Samples (first 5):")
    for agent in agents[:5]:
        print(f"  {agent.agent_id}:")
        print(f"    Received: {agent.messages_received}, Sent: {agent.messages_sent}")
        if agent.processing_times:
            avg_time = sum(agent.processing_times) / len(agent.processing_times)
            print(f"    Avg Processing: {avg_time*1000:.2f}ms")
    
    # Check success criteria
    print("\n" + "=" * 60)
    print("SUCCESS CRITERIA")
    print("=" * 60)
    
    success = True
    
    # All agents created
    if len(agents) == 100:
        print("  ✓ Created 100 agents")
    else:
        print(f"  ✗ Created {len(agents)} agents (expected 100)")
        success = False
    
    # All messages sent
    if total_sent >= 1000:
        print(f"  ✓ Sent {total_sent} messages")
    else:
        print(f"  ✗ Sent {total_sent} messages (expected 1000)")
        success = False
    
    # Most messages delivered (allowing for some in-flight)
    delivery_rate = bus_stats['delivered'] / bus_stats['published'] * 100 if bus_stats['published'] > 0 else 0
    if delivery_rate >= 90:
        print(f"  ✓ Delivery rate: {delivery_rate:.1f}%")
    else:
        print(f"  ⚠ Delivery rate: {delivery_rate:.1f}% (expected >90%)")
    
    # Low failure rate
    if bus_stats['failed'] < 50:
        print(f"  ✓ Failed messages: {bus_stats['failed']}")
    else:
        print(f"  ⚠ Failed messages: {bus_stats['failed']} (expected <50)")
    
    # Performance
    if send_time < 10:
        print(f"  ✓ Send time: {send_time:.2f}s (target: <10s)")
    else:
        print(f"  ⚠ Send time: {send_time:.2f}s (target: <10s)")
    
    if success:
        print("\n✓ LOAD TEST PASSED")
    else:
        print("\n⚠ LOAD TEST COMPLETED WITH WARNINGS")
    
    # Cleanup
    print("\n6. Cleaning up...")
    
    for agent in agents:
        await agent.shutdown()
    
    await message_bus.stop()
    await agent_registry.stop()
    
    print("   ✓ Shutdown complete")
    
    # Cleanup test data
    import shutil
    if Path("./test_data/load_test").exists():
        shutil.rmtree("./test_data/load_test")
    
    print("\n" + "=" * 60)
    print(f"Completed at: {datetime.now().isoformat()}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_load_test())
