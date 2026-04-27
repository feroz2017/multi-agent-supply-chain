import asyncio
import json
import os

from supplier_monitor import SupplierMonitorAgent
from risk_assessor import RiskAssessorAgent
from negotiator import NegotiatorAgent

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "agents.json")
PID_FILE = os.path.join(os.path.dirname(__file__), "agents.pid")

AGENT_CLASSES = {
    "SupplierMonitor": SupplierMonitorAgent,
    "RiskAssessor": RiskAssessorAgent,
    "Negotiator": NegotiatorAgent,
}


async def main():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    print("=== Supply Chain Disruption MAS ===\n")

    agents = []
    for cfg in config["agents"]:
        agent = AGENT_CLASSES[cfg["name"]](cfg["jid"], cfg["password"])
        agents.append((agent, cfg))

    for agent, cfg in agents:
        await agent.start(auto_register=True)
        agent.web.start(hostname="localhost", port=cfg["web_port"])

    agent_map = {cfg["name"]: agent for agent, cfg in agents}
    risk_assessor = agent_map["RiskAssessor"]

    print("\n--- Agents running — web UIs:")
    for _, cfg in agents:
        print(f"    {cfg['name']:<20} → http://localhost:{cfg['web_port']}/spade")
    print()

    while risk_assessor.is_alive():
        await asyncio.sleep(1)

    print("\n=== Simulation complete — web UIs still available, Ctrl+C to exit ===")
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        for agent, _ in reversed(agents):
            await agent.stop()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)


asyncio.run(main())
