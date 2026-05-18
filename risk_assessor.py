import asyncio
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

SEVERITY_THRESHOLD = 0.7
RECOVERY_TIMEOUT   = 30   # seconds to wait for a delegated recovery result


class RiskAssessorAgent(Agent):
    """
    BDI cognitive core of the MAS — coordinates recovery across both scenarios.

    Beliefs  — world model: supplier_status, port_status, inventory_level, recovery flags
    Goals    — dynamically added as alerts arrive, priority-sorted on every update
    Plans    — two plans per goal, selected based on current beliefs:
                 trigger_supplier_recovery -> plan_cnp | plan_emergency
                 trigger_route_recovery   -> plan_standard_route | plan_urgent_route

    Intention revision — before each goal is executed, stale/satisfied goals are dropped.
    """

    def __init__(self, jid, password):
        super().__init__(jid, password)

        # ── BDI: Beliefs ─────────────────────────────────────────────
        self.beliefs = {
            "supplier_status": "unknown",      # unknown | at_risk | recovered
            "port_status":     "operational",  # operational | disrupted | rerouted
            "inventory_level": "normal",       # normal | critical
            "recovery_in_progress": {
                "supplier":   False,
                "port":       False,
                "inventory":  False,
            },
        }

        # ── BDI: Goal queue ──────────────────────────────────────────
        self.goals = []

        # Track which recoveries are pending (set) — terminate when empty
        self._pending = set()
        self._ever_delegated = False

    # ─────────────────────────────────────────────────────────────────
    # BDI Behaviour
    # ─────────────────────────────────────────────────────────────────
    class BDIBehaviour(CyclicBehaviour):

        # ── Deliberation: re-sort goals by urgency ───────────────────
        def _prioritise(self):
            beliefs = self.agent.beliefs

            def priority(goal):
                g = goal[0]
                if beliefs["inventory_level"] == "critical":
                    # Supplier crisis most urgent when stock is critical
                    order = {
                        "assess_supplier_risk":      0,
                        "trigger_supplier_recovery": 1,
                        "assess_port_risk":          2,
                        "trigger_route_recovery":    3,
                    }
                else:
                    # Port strike has a hard deadline — handle first
                    order = {
                        "assess_port_risk":          0,
                        "trigger_route_recovery":    1,
                        "assess_supplier_risk":      2,
                        "trigger_supplier_recovery": 3,
                    }
                return order.get(g, 99)

            self.agent.goals.sort(key=priority)

        # ── Intention revision: drop goals already satisfied ─────────
        def _revise_intentions(self):
            agent  = self.agent
            before = len(agent.goals)
            agent.goals = [
                (g, p) for g, p in agent.goals
                if not (
                    g == "trigger_supplier_recovery"
                    and agent.beliefs["supplier_status"] == "recovered"
                ) and not (
                    g == "trigger_route_recovery"
                    and agent.beliefs["port_status"] == "rerouted"
                )
            ]
            dropped = before - len(agent.goals)
            if dropped:
                print(f"[RiskAssessor] INTENTION REVISION: "
                      f"dropped {dropped} already-satisfied goal(s)")

        # ── Plan library ─────────────────────────────────────────────

        # assess_supplier_risk -> one plan (evaluate, then queue recovery goal)
        async def _plan_assess_supplier(self, data):
            agent = self.agent
            score = data["anomaly_score"]

            if data.get("payment_delays", 0) >= 3:
                agent.beliefs["inventory_level"] = "critical"
                print("[RiskAssessor] BELIEF UPDATE: inventory_level → critical "
                      f"({data['payment_delays']} payment delays)")

            severity = "HIGH" if score >= SEVERITY_THRESHOLD else "LOW"
            agent.beliefs["supplier_status"] = "at_risk" if severity == "HIGH" else "unknown"
            print(f"[RiskAssessor] BELIEF UPDATE: supplier_status → "
                  f"{agent.beliefs['supplier_status']}")
            print(f"[RiskAssessor] Supplier {data['supplier']} — "
                  f"score={score}, severity={severity}")

            if severity == "HIGH":
                agent.goals.append(("trigger_supplier_recovery", data))
                self._prioritise()
                print(f"[RiskAssessor] GOAL ADDED: trigger_supplier_recovery "
                      f"| queue: {[g[0] for g in agent.goals]}")

        # assess_port_risk -> one plan (evaluate, then queue recovery goal)
        async def _plan_assess_port(self, data):
            agent = self.agent
            agent.beliefs["port_status"] = "disrupted"
            print(f"[RiskAssessor] BELIEF UPDATE: port_status → disrupted")
            print(f"[RiskAssessor] Port {data['port']} — "
                  f"strike_days={data['strike_days']}, score={data['disruption_score']}")

            agent.goals.append(("trigger_route_recovery", data))
            self._prioritise()
            print(f"[RiskAssessor] GOAL ADDED: trigger_route_recovery "
                  f"| queue: {[g[0] for g in agent.goals]}")

        # trigger_supplier_recovery — PLAN A: CNP only (normal inventory)
        async def _plan_recover_supplier_cnp(self, data):
            agent = self.agent
            agent.beliefs["recovery_in_progress"]["supplier"] = True
            agent._pending.add("supplier")
            agent._ever_delegated = True
            print("[RiskAssessor] BELIEF UPDATE: recovery_in_progress.supplier → True")
            print("[RiskAssessor] PLAN A — recover_supplier_cnp: "
                  "delegating to Negotiator (CNP auction)")

            msg = Message(to="negotiator@localhost")
            msg.set_metadata("performative", "request")
            msg.set_metadata("type", "find_supplier")
            msg.body = json.dumps({
                "failed_supplier": data["supplier"],
                "component":       "microchip",
                "severity":        "HIGH",
            })
            await self.send(msg)

        # trigger_supplier_recovery — PLAN B: CNP + InventoryRebalancer (critical inventory)
        async def _plan_recover_supplier_emergency(self, data):
            agent = self.agent
            agent.beliefs["recovery_in_progress"]["supplier"]  = True
            agent.beliefs["recovery_in_progress"]["inventory"] = True
            agent._pending.update({"supplier", "inventory"})
            agent._ever_delegated = True
            print("[RiskAssessor] BELIEF UPDATE: recovery_in_progress.supplier → True")
            print("[RiskAssessor] BELIEF UPDATE: recovery_in_progress.inventory → True")
            print("[RiskAssessor] PLAN B — recover_supplier_emergency: "
                  "delegating to Negotiator AND InventoryRebalancer in parallel")

            supplier_msg = Message(to="negotiator@localhost")
            supplier_msg.set_metadata("performative", "request")
            supplier_msg.set_metadata("type", "find_supplier")
            supplier_msg.body = json.dumps({
                "failed_supplier": data["supplier"],
                "component":       "microchip",
                "severity":        "HIGH",
            })
            await self.send(supplier_msg)

            inventory_msg = Message(to="inventory_rebalancer@localhost")
            inventory_msg.set_metadata("performative", "request")
            inventory_msg.set_metadata("type", "rebalance_stock")
            inventory_msg.body = json.dumps({
                "failed_supplier": data["supplier"],
                "urgency":         "HIGH",
            })
            await self.send(inventory_msg)

        # trigger_route_recovery — PLAN A: balanced scoring (no concurrent supplier crisis)
        async def _plan_recover_route_standard(self, data):
            agent = self.agent
            agent.beliefs["recovery_in_progress"]["port"] = True
            agent._pending.add("port")
            agent._ever_delegated = True
            print("[RiskAssessor] BELIEF UPDATE: recovery_in_progress.port → True")
            print("[RiskAssessor] PLAN A — recover_route_standard: "
                  "balanced scoring (cost + capacity + speed)")

            msg = Message(to="route_optimiser@localhost")
            msg.set_metadata("performative", "request")
            msg.set_metadata("type", "find_route")
            msg.body = json.dumps({
                "blocked_port":  data["port"],
                "strike_days":   data["strike_days"],
                "urgency_flag":  False,
            })
            await self.send(msg)

        # trigger_route_recovery — PLAN B: speed-first (supplier also at risk)
        async def _plan_recover_route_urgent(self, data):
            agent = self.agent
            agent.beliefs["recovery_in_progress"]["port"] = True
            agent._pending.add("port")
            agent._ever_delegated = True
            print("[RiskAssessor] BELIEF UPDATE: recovery_in_progress.port → True")
            print("[RiskAssessor] PLAN B — recover_route_urgent: "
                  "speed-first scoring (supplier also at risk — minimise transit days)")

            msg = Message(to="route_optimiser@localhost")
            msg.set_metadata("performative", "request")
            msg.set_metadata("type", "find_route")
            msg.body = json.dumps({
                "blocked_port": data["port"],
                "strike_days":  data["strike_days"],
                "urgency_flag": True,
            })
            await self.send(msg)

        # ── Plan selection ───────────────────────────────────────────
        def _select_plan(self, goal_type):
            beliefs = self.agent.beliefs

            if goal_type == "assess_supplier_risk":
                return self._plan_assess_supplier

            if goal_type == "assess_port_risk":
                return self._plan_assess_port

            if goal_type == "trigger_supplier_recovery":
                if beliefs["inventory_level"] == "critical":
                    print("[RiskAssessor] PLAN SELECTION: inventory_level=critical "
                          "-> plan_emergency (CNP + InventoryRebalancer)")
                    return self._plan_recover_supplier_emergency
                else:
                    print("[RiskAssessor] PLAN SELECTION: inventory_level=normal "
                          "-> plan_cnp (Negotiator only)")
                    return self._plan_recover_supplier_cnp

            if goal_type == "trigger_route_recovery":
                if beliefs["supplier_status"] == "at_risk":
                    print("[RiskAssessor] PLAN SELECTION: supplier_status=at_risk "
                          "-> plan_urgent_route (speed-first, both crises active)")
                    return self._plan_recover_route_urgent
                else:
                    print("[RiskAssessor] PLAN SELECTION: supplier_status=unknown "
                          "-> plan_standard_route (balanced scoring)")
                    return self._plan_recover_route_standard

            return None

        # ── Main BDI loop ────────────────────────────────────────────
        async def run(self):
            agent = self.agent

            # 1. PERCEIVE — drain all pending messages before deliberating
            #    Wait briefly after the first so in-flight messages can arrive
            msg = await self.receive(timeout=5)
            if msg:
                await asyncio.sleep(0.5)   # let any concurrent messages land
                all_msgs = [msg]
                while True:
                    m = await self.receive(timeout=0)
                    if not m:
                        break
                    all_msgs.append(m)

                for m in all_msgs:
                    msg_type = m.get_metadata("type")
                    data     = json.loads(m.body)

                    if msg_type == "supplier_alert":
                        print(f"\n[RiskAssessor] PERCEIVE: supplier_alert "
                              f"← {data['supplier']} (score={data['anomaly_score']})")
                        agent.goals.append(("assess_supplier_risk", data))
                        self._prioritise()

                    elif msg_type == "port_alert":
                        print(f"\n[RiskAssessor] PERCEIVE: port_alert "
                              f"← {data['port']} (score={data['disruption_score']})")
                        agent.goals.append(("assess_port_risk", data))
                        self._prioritise()

                    elif msg_type == "auction_result":
                        agent.beliefs["supplier_status"] = "recovered"
                        agent.beliefs["recovery_in_progress"]["supplier"] = False
                        agent._pending.discard("supplier")
                        print(f"\n[RiskAssessor] PERCEIVE: auction_result — "
                              f"winner={data['winner']}, price=${data['price']}, "
                              f"lead_days={data['lead_days']}")
                        print("[RiskAssessor] BELIEF UPDATE: supplier_status → recovered")

                    elif msg_type == "rebalance_result":
                        agent.beliefs["recovery_in_progress"]["inventory"] = False
                        agent._pending.discard("inventory")
                        print(f"\n[RiskAssessor] PERCEIVE: rebalance_result — "
                              f"status={data['status']}, "
                              f"transfers={len(data.get('transfers', []))}")
                        print("[RiskAssessor] BELIEF UPDATE: recovery_in_progress.inventory → False")

                    elif msg_type == "route_result":
                        agent.beliefs["port_status"] = "rerouted"
                        agent.beliefs["recovery_in_progress"]["port"] = False
                        agent._pending.discard("port")
                        print(f"\n[RiskAssessor] PERCEIVE: route_result — "
                              f"alt_port={data['port']}, "
                              f"extra_days={data['extra_transit_days']}")
                        print("[RiskAssessor] BELIEF UPDATE: port_status → rerouted")

            # 2. INTENTION REVISION — drop goals whose conditions are already met
            self._revise_intentions()

            # 3. DELIBERATE — detect and resolve conflicting goals
            if len(agent.goals) >= 2:
                goal_names = [g[0] for g in agent.goals]
                print(f"\n[RiskAssessor] *** CONFLICTING GOALS DETECTED: {goal_names}")
                print(f"[RiskAssessor] DELIBERATE: "
                      f"inventory_level={agent.beliefs['inventory_level']}, "
                      f"supplier_status={agent.beliefs['supplier_status']}")
                self._prioritise()
                print(f"[RiskAssessor] PRIORITY ORDER: "
                      f"{[g[0] for g in agent.goals]}")

            # 4. ACT — execute highest-priority goal
            if agent.goals:
                goal_type, payload = agent.goals.pop(0)
                print(f"\n[RiskAssessor] EXECUTE: {goal_type}")
                plan = self._select_plan(goal_type)
                if plan:
                    await plan(payload)

            # 5. TERMINATE — all delegated recoveries have reported back
            if (agent._ever_delegated
                    and not agent._pending
                    and not agent.goals):
                print(f"\n[RiskAssessor] ✓ All goals satisfied. Final beliefs:")
                for k, v in agent.beliefs.items():
                    print(f"[RiskAssessor]   {k}: {v}")
                self.kill()

    async def setup(self):
        print("[RiskAssessor] Agent started — BDI initialised")
        print(f"[RiskAssessor] Initial beliefs: {self.beliefs}")
        self.add_behaviour(self.BDIBehaviour())
