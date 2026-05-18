import json
import random
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message


class SupplierAgent(Agent):
    """
    Reactive supplier agent participating in the Contract Net Protocol auction.
    Waits for a CFP, replies with a randomised PROPOSE, then handles ACCEPT/REJECT.
    Three instances (Korea, Germany, SEA) represent the candidate suppliers.
    """

    def __init__(self, jid, password, name, base_price, base_lead_days,
                 base_reliability, region):
        super().__init__(jid, password)
        self.supplier_name    = name
        self.base_price       = base_price
        self.base_lead_days   = base_lead_days
        self.base_reliability = base_reliability
        self.region           = region

    class CNPBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=60)
            if not msg:
                return

            msg_type = msg.get_metadata("type")

            if msg_type == "cfp":
                # Slight randomness in each bid — outcomes vary each run
                price       = round(self.agent.base_price * random.uniform(0.95, 1.05))
                lead_days   = max(1, self.agent.base_lead_days + random.randint(-1, 1))
                reliability = round(
                    min(1.0, self.agent.base_reliability + random.uniform(-0.02, 0.02)), 2
                )

                print(f"[{self.agent.supplier_name}] CFP received → PROPOSE "
                      f"${price}, {lead_days}d, reliability={reliability}")

                reply = Message(to=str(msg.sender))
                reply.set_metadata("performative", "propose")
                reply.set_metadata("type", "bid")
                reply.body = json.dumps({
                    "name":        self.agent.supplier_name,
                    "price":       price,
                    "lead_days":   lead_days,
                    "reliability": reliability,
                    "region":      self.agent.region,
                })
                await self.send(reply)

            elif msg_type == "contract_awarded":
                print(f"[{self.agent.supplier_name}] ✓ ACCEPT received — contract awarded")

            elif msg_type == "contract_rejected":
                print(f"[{self.agent.supplier_name}] REJECT received — not selected")

    async def setup(self):
        print(f"[{self.supplier_name}] Supplier agent started")
        self.add_behaviour(self.CNPBehaviour())


# Config for the three candidate suppliers used in the CNP auction
SUPPLIER_CONFIGS = [
    {
        "name": "KoreaPartsLtd", "jid": "korea_parts@localhost",
        "password": "koreapass",
        "base_price": 120, "base_lead_days": 7, "base_reliability": 0.91,
        "region": "korea",
    },
    {
        "name": "GermanTechGmbH", "jid": "german_tech@localhost",
        "password": "germanpass",
        "base_price": 145, "base_lead_days": 5, "base_reliability": 0.95,
        "region": "europe",
    },
    {
        "name": "SunriseSemicorp", "jid": "sunrise_semi@localhost",
        "password": "sunrisepass",
        "base_price": 98, "base_lead_days": 10, "base_reliability": 0.78,
        "region": "sea",
    },
]
