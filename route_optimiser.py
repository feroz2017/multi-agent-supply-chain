import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

# Mock alternate routes. region is shared with Negotiator (cross-scenario cooperation).
ALTERNATE_ROUTES = [
    {
        "port":               "PortOfBusan",
        "extra_transit_days": 3,
        "capacity_pct":       0.85,
        "cost_index":         1.12,
        "region":             "korea",
    },
    {
        "port":               "PortOfShanghai",
        "extra_transit_days": 2,
        "capacity_pct":       0.70,
        "cost_index":         1.08,
        "region":             "china",
    },
    {
        "port":               "PortOfSingapore",
        "extra_transit_days": 5,
        "capacity_pct":       0.95,
        "cost_index":         1.25,
        "region":             "sea",
    },
]


def score_route(route, urgent=False):
    """
    urgent=False (standard): balance capacity, transit time, and cost.
    urgent=True  (emergency): prioritise minimum transit days — speed over cost.
    Triggered when RiskAssessor knows supplier is ALSO at risk (both crises active).
    """
    if urgent:
        # Speed-first: minimise transit days, partial weight on capacity
        return -route["extra_transit_days"] + route["capacity_pct"] * 0.5
    return (
        route["capacity_pct"]
        - (route["extra_transit_days"] / 20)
        - (route["cost_index"] / 10)
    )


class RouteOptimiserAgent(Agent):
    """
    Scenario 2 — evaluates alternate shipping routes when the primary port
    is blocked. RiskAssessor sets urgency_flag=True when supplier failure is
    also active, triggering speed-first scoring instead of balanced scoring.
    """

    class OptimiseBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=30)
            if not msg or msg.get_metadata("type") != "find_route":
                return

            data   = json.loads(msg.body)
            urgent = data.get("urgency_flag", False)

            print(
                f"[RouteOptimiser] Received task — reroute away from "
                f"{data['blocked_port']} ({data['strike_days']}-day strike)"
            )
            print(
                f"[RouteOptimiser] Strategy: "
                f"{'URGENT — speed-first (supplier also at risk)' if urgent else 'standard — balanced scoring'}"
            )
            print(f"[RouteOptimiser] Evaluating {len(ALTERNATE_ROUTES)} alternate routes...")

            for r in ALTERNATE_ROUTES:
                s = score_route(r, urgent=urgent)
                print(
                    f"[RouteOptimiser]   {r['port']:<22}  "
                    f"extra={r['extra_transit_days']}d  "
                    f"capacity={r['capacity_pct']}  "
                    f"cost_idx={r['cost_index']}  "
                    f"→ score={s:.4f}"
                )

            best = max(ALTERNATE_ROUTES, key=lambda r: score_route(r, urgent=urgent))
            print(f"[RouteOptimiser] ✓ Best route selected: {best['port']} "
                  f"(region={best['region']})")

            # Cross-scenario cooperation: tell Negotiator the selected port region
            # so it can prefer suppliers geographically close to the rerouted port.
            hint = Message(to="negotiator@localhost")
            hint.set_metadata("performative", "inform")
            hint.set_metadata("type", "port_hint")
            hint.body = json.dumps({"port": best["port"], "region": best["region"]})
            await self.send(hint)
            print(f"[RouteOptimiser] Cross-scenario hint → Negotiator: "
                  f"prefer '{best['region']}' region suppliers")

            result = Message(to="risk_assessor@localhost")
            result.set_metadata("performative", "inform")
            result.set_metadata("type", "route_result")
            result.body = json.dumps({
                "port":               best["port"],
                "extra_transit_days": best["extra_transit_days"],
                "capacity_pct":       best["capacity_pct"],
            })
            await self.send(result)
            print("[RouteOptimiser] Route result sent to RiskAssessor")

    async def setup(self):
        print("[RouteOptimiser] Agent started")
        self.add_behaviour(self.OptimiseBehaviour())
