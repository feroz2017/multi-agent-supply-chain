# Multi-Agent Supply Chain System

A multi-agent system built with [SPADE](https://spade-mas.readthedocs.io/) (Python 3.12) that handles two simultaneous supply chain disruptions. Agents communicate over XMPP, use BDI reasoning, and run a real Contract Net Protocol auction.

---

## Agents

```mermaid
flowchart TB
    subgraph MONITORS["MONITORS — observe and report"]
        SM["SupplierMonitor\nWatches supplier signals"]
        LM["LogisticsMonitor\nWatches port operations"]
    end

    subgraph BRAIN["BRAIN — thinks and decides"]
        RA["RiskAssessor\nBDI Agent — Beliefs, Goals, Plans"]
    end

    subgraph SPECIALISTS["SPECIALISTS — execute recovery"]
        NE["Negotiator\nBDI Agent — runs CNP auction"]
        RO["RouteOptimiser\nScores alternate ports"]
        IR["InventoryRebalancer\nRedistributes warehouse stock"]
    end

    subgraph SUPPLIERS["SUPPLIER AGENTS — respond to auction"]
        S1["KoreaPartsLtd"]
        S2["GermanTechGmbH"]
        S3["SunriseSemicorp"]
    end

    SM -->|supplier_alert| RA
    LM -->|port_alert| RA
    RA -->|find_supplier| NE
    RA -->|find_route| RO
    RA -->|rebalance_stock| IR
    NE -->|CFP| S1 & S2 & S3
    S1 & S2 & S3 -->|PROPOSE| NE
    RO -->|port_hint| NE
```

---

## Scenarios

**Scenario 1 — Supplier Disruption**

TaiwanChipCo shows payment delays. RiskAssessor assesses severity and either runs a CNP auction (normal inventory) or triggers both the auction and a stock rebalance in parallel (critical inventory).

**Scenario 2 — Port Strike**

Port of Manila announces a strike. RiskAssessor picks a recovery plan based on whether a supplier crisis is also active — balanced scoring normally, speed-only if urgent. The selected port region is forwarded to Negotiator as a proximity hint.

---

## BDI Loop

```mermaid
flowchart TD
    START(["RiskAssessor wakes up"])

    START --> P["PERCEIVE\nDrain all incoming messages\nUpdate beliefs for each one"]

    P --> R["REVISE INTENTIONS\nDrop goals that are already satisfied"]

    R --> D["DELIBERATE\nIf two goals conflict, pick priority\nbased on inventory_level belief"]

    D --> A["ACT\nPop top goal, select plan, execute"]

    A --> T{"All done?"}
    T -->|"yes"| DONE(["Terminate"])
    T -->|"no"| START
```

---

## Cross-Scenario Cooperation

RouteOptimiser (Scenario 2) sends a `port_hint` to Negotiator (Scenario 1). If the hint is available, Negotiator applies a proximity bonus to suppliers in the same region as the selected port. This can change the auction winner.

```mermaid
flowchart LR
    RO["RouteOptimiser\nSelects: Port of Busan\nRegion: Korea"]
    MSG["port_hint\nregion = korea"]
    NE["Negotiator\nUpdates auction strategy\nto regional preferred"]
    BID["KoreaPartsLtd gets +0.05 bonus\nand wins the auction"]

    RO -->|sends| MSG
    MSG -->|received by| NE
    NE --> BID
```

---

## Requirements

- Python 3.12 (not 3.13 — SPADE is incompatible)
- Docker

---

## Setup

**1. Create a virtual environment with Python 3.12**

```bash
python3.12 -m venv venv
source venv/bin/activate
```

**2. Install dependencies**

```bash
pip install spade packaging
```

---

## How to Run

**Step 1 — Start the XMPP server (Docker)**

```bash
./spade-setup/start-spade.sh
```

Wait a few seconds for Prosody to start before running agents.

**Step 2 — Run the simulation**

```bash
python -u main.py
```

The `-u` flag disables output buffering so you see logs in real time.

**Step 3 — Stop everything**

```bash
./spade-setup/stop-spade.sh
```

---

## Web UIs

Available while the simulation is running:

| Agent               | URL                           |
|---------------------|-------------------------------|
| SupplierMonitor     | http://localhost:10005/spade  |
| LogisticsMonitor    | http://localhost:10004/spade  |
| RiskAssessor        | http://localhost:10003/spade  |
| Negotiator          | http://localhost:10002/spade  |
| RouteOptimiser      | http://localhost:10001/spade  |
| InventoryRebalancer | http://localhost:10000/spade  |

Supplier agents (KoreaPartsLtd, GermanTechGmbH, SunriseSemicorp) run in the background with no web UI.

---

## Project Structure

```
main.py                 — starts all agents
agents.json             — JIDs, passwords, web ports for main agents
risk_assessor.py        — BDI agent (core decision maker)
negotiator.py           — BDI agent (CNP auction)
supplier_monitor.py     — detects supplier anomalies
logistics_monitor.py    — detects port disruptions
route_optimiser.py      — scores alternate ports
inventory_rebalancer.py — redistributes warehouse stock
supplier_agents.py      — KoreaPartsLtd, GermanTechGmbH, SunriseSemicorp
diagrams-html/          — 9 presentation slides (open in browser)
```
