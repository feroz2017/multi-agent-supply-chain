import json
import time
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

REGIONAL_PROXIMITY_BONUS = 0.05
CFP_TIMEOUT = 5  # seconds to wait for all supplier proposals

# JIDs of the three candidate supplier agents
SUPPLIER_JIDS = [
    "korea_parts@localhost",
    "german_tech@localhost",
    "sunrise_semi@localhost",
]

JID_TO_NAME = {
    "korea_parts@localhost":  "KoreaPartsLtd",
    "german_tech@localhost":  "GermanTechGmbH",
    "sunrise_semi@localhost": "SunriseSemicorp",
}


def score_bid(bid, preferred_region=None):
    """Higher reliability and lower price/lead-time = better score.
    Divisors normalise each term to a 0–1 scale comparable to reliability."""
    score = bid["reliability"] - (bid["price"] / 1000) - (bid["lead_days"] / 100)
    if preferred_region and bid.get("region") == preferred_region:
        score += REGIONAL_PROXIMITY_BONUS
    return score


class NegotiatorAgent(Agent):
    """
    BDI Negotiator — runs the Contract Net Protocol auction.

    Beliefs  — port_region_hint (from RouteOptimiser), auction_strategy, auction_active
    Goals    — run_cnp_auction
    Plans    — plan_standard_auction | plan_regional_auction (selected on beliefs)

    Cross-scenario cooperation: RouteOptimiser sends a port_hint before the
    auction runs. If available, the Negotiator switches to plan_regional_auction
    which applies a proximity bonus to suppliers near the rerouted port.
    """

    def __init__(self, jid, password):
        super().__init__(jid, password)

        # ── BDI: Beliefs ─────────────────────────────────────────────
        self.beliefs = {
            "port_region_hint": None,        # set by RouteOptimiser cross-scenario hint
            "auction_strategy": "balanced",  # balanced | regional_preferred
            "auction_active":   False,
        }

        # ── BDI: Goals ───────────────────────────────────────────────
        self.goals = []

    class BDIBehaviour(CyclicBehaviour):

        # ── Plan selection ───────────────────────────────────────────
        def _select_plan(self):
            """Choose plan based on current beliefs — the core of BDI plan selection."""
            if self.agent.beliefs["port_region_hint"]:
                print(f"[Negotiator] PLAN SELECTED: regional_auction "
                      f"(port_region_hint='{self.agent.beliefs['port_region_hint']}' "
                      f"→ proximity bonus available)")
                return self._plan_regional_auction
            print("[Negotiator] PLAN SELECTED: standard_auction "
                  "(no region hint → pure score-based selection)")
            return self._plan_standard_auction

        # ── Shared: broadcast CFP and collect real PROPOSE messages ──
        async def _broadcast_and_collect(self, task_data):
            print(f"[Negotiator] Broadcasting CFP to "
                  f"{len(SUPPLIER_JIDS)} supplier agents...")

            for jid in SUPPLIER_JIDS:
                cfp = Message(to=jid)
                cfp.set_metadata("performative", "call-for-proposals")
                cfp.set_metadata("type", "cfp")
                cfp.body = json.dumps({
                    "component":       task_data.get("component", "microchip"),
                    "failed_supplier": task_data.get("failed_supplier"),
                })
                await self.send(cfp)

            # Collect PROPOSE messages within the timeout window
            bids     = []
            deadline = time.monotonic() + CFP_TIMEOUT
            while time.monotonic() < deadline and len(bids) < len(SUPPLIER_JIDS):
                remaining = max(0.1, deadline - time.monotonic())
                msg = await self.receive(timeout=remaining)
                if msg and msg.get_metadata("type") == "bid":
                    bids.append(json.loads(msg.body))

            print(f"[Negotiator] Collected {len(bids)}/{len(SUPPLIER_JIDS)} proposals")
            return bids

        # ── Shared: award contract, send ACCEPT/REJECT ───────────────
        async def _award_contract(self, winner, all_bids):
            print(f"[Negotiator] ✓ Contract awarded to {winner['name']}")

            name_to_jid = {v: k for k, v in JID_TO_NAME.items()}
            for bid in all_bids:
                target_jid = name_to_jid.get(bid["name"])
                if not target_jid:
                    continue
                reply = Message(to=target_jid)
                if bid["name"] == winner["name"]:
                    reply.set_metadata("performative", "accept-proposal")
                    reply.set_metadata("type", "contract_awarded")
                else:
                    reply.set_metadata("performative", "reject-proposal")
                    reply.set_metadata("type", "contract_rejected")
                reply.body = json.dumps({"winner": winner["name"]})
                await self.send(reply)

            result = Message(to="risk_assessor@localhost")
            result.set_metadata("performative", "inform")
            result.set_metadata("type", "auction_result")
            result.body = json.dumps({
                "winner":    winner["name"],
                "price":     winner["price"],
                "lead_days": winner["lead_days"],
            })
            await self.send(result)
            print("[Negotiator] Auction result sent to RiskAssessor")

        # ── Plan A: standard auction (no region preference) ──────────
        async def _plan_standard_auction(self, data):
            bids = await self._broadcast_and_collect(data)
            if not bids:
                print("[Negotiator] No proposals received — auction failed")
                return

            for bid in bids:
                s = score_bid(bid)
                print(f"[Negotiator]   {bid['name']:<18} ${bid['price']}  "
                      f"{bid['lead_days']}d  reliability={bid['reliability']}  "
                      f"→ score={s:.4f}")

            winner = max(bids, key=score_bid)
            await self._award_contract(winner, bids)

        # ── Plan B: regional auction (proximity bonus applied) ───────
        async def _plan_regional_auction(self, data):
            hint = self.agent.beliefs["port_region_hint"]
            bids = await self._broadcast_and_collect(data)
            if not bids:
                print("[Negotiator] No proposals received — auction failed")
                return

            for bid in bids:
                base  = score_bid(bid)
                bonus = REGIONAL_PROXIMITY_BONUS if bid.get("region") == hint else 0
                final = base + bonus
                tag   = f"  +{bonus} regional bonus" if bonus else ""
                print(f"[Negotiator]   {bid['name']:<18} ${bid['price']}  "
                      f"{bid['lead_days']}d  reliability={bid['reliability']}  "
                      f"→ score={final:.4f}{tag}")

            winner = max(bids, key=lambda b: score_bid(b, hint))
            await self._award_contract(winner, bids)

        # ── Main BDI loop ────────────────────────────────────────────
        async def run(self):
            agent = self.agent

            msg = await self.receive(timeout=60)
            if not msg:
                return

            msg_type = msg.get_metadata("type")
            data     = json.loads(msg.body)

            # PERCEIVE + BELIEVE: cross-scenario hint from RouteOptimiser
            if msg_type == "port_hint":
                agent.beliefs["port_region_hint"] = data["region"]
                agent.beliefs["auction_strategy"] = "regional_preferred"
                print(f"\n[Negotiator] PERCEIVE: port_hint ← RouteOptimiser "
                      f"(region='{data['region']}')")
                print(f"[Negotiator] BELIEF UPDATE: port_region_hint → {data['region']}")
                print(f"[Negotiator] BELIEF UPDATE: auction_strategy → regional_preferred")
                return

            if msg_type != "find_supplier":
                return

            # GOAL added
            print(f"\n[Negotiator] PERCEIVE: find_supplier task received")
            agent.goals.append(("run_cnp_auction", data))
            agent.beliefs["auction_active"] = True
            print(f"[Negotiator] BELIEF UPDATE: auction_active → True")
            print(f"[Negotiator] GOAL ADDED: run_cnp_auction")

            # PLAN SELECTION based on beliefs
            plan = self._select_plan()
            await plan(data)

            # Goal resolved
            agent.beliefs["auction_active"] = False
            agent.goals.clear()
            print(f"[Negotiator] BELIEF UPDATE: auction_active → False")

    async def setup(self):
        print("[Negotiator] Agent started — BDI initialised")
        print(f"[Negotiator] Initial beliefs: {self.beliefs}")
        self.add_behaviour(self.BDIBehaviour())
