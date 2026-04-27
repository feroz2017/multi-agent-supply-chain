import asyncio
import json
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message


class SupplierMonitorAgent(Agent):

    class DetectAnomaly(OneShotBehaviour):
        async def run(self):
            print("[SupplierMonitor] Scanning supplier signals...")
            await asyncio.sleep(2)

            # Fake supplier anomaly data
            anomaly = {
                "supplier": "TaiwanChipCo",
                "credit_rating_drop": True,
                "payment_delays": 3,
                "anomaly_score": 0.82,
            }

            print(f"[SupplierMonitor] Anomaly detected — {anomaly['supplier']} "
                  f"(score={anomaly['anomaly_score']})")

            msg = Message(to="risk_assessor@localhost")
            msg.set_metadata("performative", "inform")
            msg.set_metadata("type", "supplier_alert")
            msg.body = json.dumps(anomaly)

            await self.send(msg)
            print("[SupplierMonitor] Alert sent to RiskAssessor")

    async def setup(self):
        print("[SupplierMonitor] Agent started")
        self.add_behaviour(self.DetectAnomaly())
