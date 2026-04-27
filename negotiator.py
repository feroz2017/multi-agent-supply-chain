import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

# Mock supplier bids (Contract Net Protocol simulation)
MOCK_BIDS = [
    {"name": "KoreaPartsLtd",  "price": 120, "lead_days": 7,  "reliability": 0.91},
    {"name": "GermanTechGmbH", "price": 145, "lead_days": 5,  "reliability": 0.95},
    {"name": "IndiaChipWorks", "price": 98,  "lead_days": 10, "reliability": 0.78},
]


def score_bid(bid):
    # Higher reliability and lower price/lead-time = better score
    return bid["reliability"] - (bid["price"] / 1000) - (bid["lead_days"] / 100)


class NegotiatorAgent(Agent):

    class AuctionBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=30)
            if not msg or msg.get_metadata("type") != "find_supplier":
                return

            data = json.loads(msg.body)
            print(f"[Negotiator] Received task — find supplier for {data['component']} "
                  f"(replacing {data['failed_supplier']})")
            print(f"[Negotiator] Broadcasting CFP to {len(MOCK_BIDS)} candidates...")

            for bid in MOCK_BIDS:
                print(f"[Negotiator]   PROPOSE from {bid['name']}: "
                      f"${bid['price']}, {bid['lead_days']}d, "
                      f"reliability={bid['reliability']}")

            winner = max(MOCK_BIDS, key=score_bid)
            print(f"[Negotiator] Contract awarded to {winner['name']}")

            result = Message(to="risk_assessor@localhost")
            result.set_metadata("performative", "inform")
            result.set_metadata("type", "auction_result")
            result.body = json.dumps({
                "winner": winner["name"],
                "price": winner["price"],
                "lead_days": winner["lead_days"],
            })
            await self.send(result)
            print("[Negotiator] Result sent to RiskAssessor")

    async def setup(self):
        print("[Negotiator] Agent started")
        self.add_behaviour(self.AuctionBehaviour())
