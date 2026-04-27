import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

SEVERITY_THRESHOLD = 0.7


class RiskAssessorAgent(Agent):

    class AssessBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=30)
            if not msg:
                return

            msg_type = msg.get_metadata("type")

            if msg_type == "supplier_alert":
                data = json.loads(msg.body)
                score = data["anomaly_score"]

                # Autonomous decision: classify severity from score
                severity = "HIGH" if score >= SEVERITY_THRESHOLD else "LOW"
                print(f"[RiskAssessor] Received alert for {data['supplier']} — "
                      f"score={score}, severity={severity}")

                if severity == "HIGH":
                    print("[RiskAssessor] Delegating supplier search to Negotiator")
                    delegate = Message(to="negotiator@localhost")
                    delegate.set_metadata("performative", "request")
                    delegate.set_metadata("type", "find_supplier")
                    delegate.body = json.dumps({
                        "failed_supplier": data["supplier"],
                        "component": "microchip",
                        "severity": severity,
                    })
                    await self.send(delegate)
                else:
                    print("[RiskAssessor] Severity LOW — no action taken")

            elif msg_type == "auction_result":
                result = json.loads(msg.body)
                print(f"[RiskAssessor] Recovery complete — "
                      f"winner={result['winner']}, price=${result['price']}, "
                      f"lead_days={result['lead_days']}")
                self.kill()

    async def setup(self):
        print("[RiskAssessor] Agent started")
        self.add_behaviour(self.AssessBehaviour())
