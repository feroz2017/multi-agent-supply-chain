import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

# Mock warehouse inventory (units on hand vs safety-stock minimum)
WAREHOUSES = {
    "EU-West": {"stock": 450, "safety_stock": 200},
    "APAC":    {"stock": 120, "safety_stock": 150},   # below safety stock
    "US-East": {"stock": 380, "safety_stock": 200},
}


class InventoryRebalancerAgent(Agent):
    """
    Scenario 1 — parallel recovery stream.

    Triggered by RiskAssessor when inventory_level is CRITICAL (plan_emergency).
    Redistributes existing stock across warehouses while the Negotiator
    sources a replacement supplier, covering the supply gap in the interim.
    """

    class RebalanceBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=60)
            if not msg or msg.get_metadata("type") != "rebalance_stock":
                return

            data = json.loads(msg.body)
            print(f"\n[InventoryRebalancer] Rebalance request received "
                  f"(urgency={data['urgency']})")
            print("[InventoryRebalancer] Assessing warehouse levels...")

            for name, wh in WAREHOUSES.items():
                flag = "⚠ BELOW SAFETY" if wh["stock"] < wh["safety_stock"] else "OK"
                print(f"[InventoryRebalancer]   {name:<12} "
                      f"stock={wh['stock']}  safety={wh['safety_stock']}  [{flag}]")

            # Identify surplus (can donate) and deficit (needs stock)
            surplus = {k: v for k, v in WAREHOUSES.items()
                       if v["stock"] >= v["safety_stock"] + 100}
            deficit = {k: v for k, v in WAREHOUSES.items()
                       if v["stock"] < v["safety_stock"]}

            transfers = []
            for d_name, d_wh in deficit.items():
                for s_name, s_wh in surplus.items():
                    qty = min(
                        s_wh["stock"] - s_wh["safety_stock"] - 50,
                        d_wh["safety_stock"] - d_wh["stock"] + 50,
                    )
                    if qty > 0:
                        transfers.append({"from": s_name, "to": d_name, "qty": qty})
                        print(f"[InventoryRebalancer]   Transfer: "
                              f"{qty} units  {s_name} → {d_name}")

            if not transfers:
                print("[InventoryRebalancer]   No transfers needed")

            print(f"[InventoryRebalancer] ✓ Rebalance complete — "
                  f"{len(transfers)} transfer(s) ordered")

            result = Message(to="risk_assessor@localhost")
            result.set_metadata("performative", "inform")
            result.set_metadata("type", "rebalance_result")
            result.body = json.dumps({
                "status":    "rebalanced" if transfers else "no_action_needed",
                "transfers": transfers,
            })
            await self.send(result)
            print("[InventoryRebalancer] Result sent to RiskAssessor")

    async def setup(self):
        print("[InventoryRebalancer] Agent started")
        self.add_behaviour(self.RebalanceBehaviour())
