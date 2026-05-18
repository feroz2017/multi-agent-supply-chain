import asyncio
import json
import random
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message


class SupplierMonitorAgent(Agent):

    class DetectAnomaly(OneShotBehaviour):
        async def run(self):
            print("[SupplierMonitor] Scanning supplier signals...")
            await asyncio.sleep(2)

            # Randomised each run — outcomes vary so plan selection is non-deterministic
            anomaly = {
                "supplier":           "TaiwanChipCo",
                "credit_rating_drop": True,
                "payment_delays":     random.randint(1, 5),
                "anomaly_score":      round(random.uniform(0.72, 0.95), 2),
            }

            print(f"[SupplierMonitor] Anomaly detected — {anomaly['supplier']} "
                  f"(score={anomaly['anomaly_score']}, "
                  f"payment_delays={anomaly['payment_delays']})")

            msg = Message(to="risk_assessor@localhost")
            msg.set_metadata("performative", "inform")
            msg.set_metadata("type", "supplier_alert")
            msg.body = json.dumps(anomaly)

            await self.send(msg)
            print("[SupplierMonitor] Alert sent to RiskAssessor")

    async def setup(self):
        print("[SupplierMonitor] Agent started")
        self.add_behaviour(self.DetectAnomaly())
