import asyncio
import json
import os

from supplier_monitor    import SupplierMonitorAgent
from logistics_monitor   import LogisticsMonitorAgent
from risk_assessor       import RiskAssessorAgent
from negotiator          import NegotiatorAgent
from route_optimiser     import RouteOptimiserAgent
from inventory_rebalancer import InventoryRebalancerAgent
from supplier_agents     import SupplierAgent, SUPPLIER_CONFIGS

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "agents.json")
PID_FILE    = os.path.join(os.path.dirname(__file__), "agents.pid")

AGENT_CLASSES = {
    "SupplierMonitor":    SupplierMonitorAgent,
    "LogisticsMonitor":   LogisticsMonitorAgent,
    "RiskAssessor":       RiskAssessorAgent,
    "Negotiator":         NegotiatorAgent,
    "RouteOptimiser":     RouteOptimiserAgent,
    "InventoryRebalancer": InventoryRebalancerAgent,
}


async def main():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    print("=== Supply Chain Disruption MAS ===")
    print("    Scenario 1: Supplier Disruption  "
          "(SupplierMonitor → RiskAssessor → Negotiator [+ InventoryRebalancer if critical])")
    print("    Scenario 2: Port Labour Stoppage "
          "(LogisticsMonitor → RiskAssessor → RouteOptimiser)")
    print()

    # ── Start main agents (with web UIs) ────────────────────────────
    agents = []
    for cfg in config["agents"]:
        agent = AGENT_CLASSES[cfg["name"]](cfg["jid"], cfg["password"])
        agents.append((agent, cfg))

    for agent, cfg in agents:
        await agent.start(auto_register=True)
        agent.web.start(hostname="localhost", port=cfg["web_port"])

    # ── Start supplier agents (background — no web UI) ───────────────
    supplier_agents = []
    for cfg in SUPPLIER_CONFIGS:
        s = SupplierAgent(
            jid              = cfg["jid"],
            password         = cfg["password"],
            name             = cfg["name"],
            base_price       = cfg["base_price"],
            base_lead_days   = cfg["base_lead_days"],
            base_reliability = cfg["base_reliability"],
            region           = cfg["region"],
        )
        supplier_agents.append(s)
        await s.start(auto_register=True)

    agent_map    = {cfg["name"]: agent for agent, cfg in agents}
    risk_assessor = agent_map["RiskAssessor"]

    print("\n--- Agents running — web UIs:")
    for _, cfg in agents:
        print(f"    {cfg['name']:<22} → http://localhost:{cfg['web_port']}/spade")
    print(f"\n    Supplier agents (background, no UI):")
    for cfg in SUPPLIER_CONFIGS:
        print(f"    {cfg['name']}")
    print()

    # Wait for RiskAssessor to finish (it kills itself when all goals are met)
    while risk_assessor.is_alive():
        await asyncio.sleep(1)

    print("\n=== Simulation complete — web UIs still available, Ctrl+C to exit ===")
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        for s in supplier_agents:
            await s.stop()
        for agent, _ in reversed(agents):
            await agent.stop()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)


asyncio.run(main())
