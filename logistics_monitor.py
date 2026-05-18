import asyncio
import json
import random
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message


class LogisticsMonitorAgent(Agent):
    """
    Scenario 2 — Port Labour Stoppage.
    Monitors port operations and notifies RiskAssessor when a disruption is detected.
    """

    class DetectPortDisruption(OneShotBehaviour):
        async def run(self):
            print("[LogisticsMonitor] Monitoring port operations...")
            # Fire at same time as SupplierMonitor to trigger conflicting goals
            await asyncio.sleep(2)

            # Randomised each run
            disruption = {
                "port":             "PortOfManila",
                "type":             "labour_strike",
                "strike_days":      random.randint(7, 14),
                "disruption_score": round(random.uniform(0.80, 0.95), 2),
                "affected_routes":  ["APAC-EU-1", "APAC-EU-3"],
            }

            print(
                f"[LogisticsMonitor] : Port disruption detected — "
                f"{disruption['port']} "
                f"(strike={disruption['strike_days']} days, "
                f"score={disruption['disruption_score']})"
            )

            msg = Message(to="risk_assessor@localhost")
            msg.set_metadata("performative", "inform")
            msg.set_metadata("type", "port_alert")
            msg.body = json.dumps(disruption)

            await self.send(msg)
            print("[LogisticsMonitor] Port alert sent to RiskAssessor")

    async def setup(self):
        print("[LogisticsMonitor] Agent started")
        self.add_behaviour(self.DetectPortDisruption())
