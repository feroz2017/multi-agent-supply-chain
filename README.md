# Multi-agent-supply-chain

A multi-agent system for supply chain disruption management built with [SPADE](https://spade-mas.readthedocs.io/) (Python). Three autonomous agents communicate via XMPP messaging to detect a supplier failure, assess risk, and negotiate a replacement contract.

**Agents:** `SupplierMonitor` → `RiskAssessor` → `Negotiator`

---

## Requirements

- Python 3.12+
- Docker

---

## Setup

**1. Create and activate a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

**2. Install dependencies**

```bash
pip install spade
```

---

## Running

**1. Start the XMPP server**

```bash
./spade-setup/start-spade.sh
```

**2. Run the agents**

```bash
python main.py
```

The console will show each agent's activity as messages flow through the system.

**3. Stop everything**

```bash
./spade-setup/stop-spade.sh
```

This stops both the agent process and the XMPP server.

---

## Agent config

JIDs, passwords, and web UI ports are defined in [`agents.json`](agents.json).
# multi-agent-supply-chain
