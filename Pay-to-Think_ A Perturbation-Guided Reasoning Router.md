# **Pay-to-Think: A Perturbation-Guided Reasoning Router**

## **One-line idea**

Build an agent that treats **reasoning as a resource it must decide whether to purchase**: start with a cheap inference pass, estimate whether the current decision is unstable, and invoke expensive reasoning only when the expected benefit appears worth the token cost.

For the hackathon, Texas Hold’em provides a compact and visual environment for demonstrating this idea: every agent has a finite token bankroll, and deeper reasoning literally costs some of that bankroll.

---

## **Why this is interesting for us**

This is closely related to the motivation behind **Perturbation Probing**.

Perturbation Probing asks whether small, controlled interventions reveal where a model's behavior is sensitive. Here we move that idea one level upward:

> Can cheap perturbations tell us **when a model's current answer is sensitive enough that we should pay for more reasoning?**

Instead of perturbing activations to locate FFN behavioral circuits, the hackathon version can perturb the **input or cheap inference trajectory** and use behavioral instability as a routing signal.

The general workflow becomes:

**cheap inference → perturb → measure stability → decide whether to think harder → act**

The key hypothesis is simple:

> If several cheap, nearby versions of a decision all produce essentially the same behavior, additional reasoning often has low marginal value. If a small perturbation changes the decision, confidence, or action substantially, the example may deserve a larger reasoning budget.

This is not intended as a theorem about reasoning. It is a practical routing heuristic that we can test very quickly.

---

## **Why Hold’em is a good demo environment**

Poker makes the otherwise abstract concept of inference-time compute immediately understandable.

An agent has two scarce resources:

* chips representing game wealth;  
* tokens representing the cost of intelligence.

On each turn, it can either:

* **Act now** using the cheap result;  
* **Pay to think** using a larger reasoning budget;  
* optionally **pay to use a tool**, such as an equity simulation.

This produces a natural decision problem:

> Is this situation important and uncertain enough to justify spending more intelligence on it?

Poker is particularly useful because it contains:

* asymmetric information;  
* repeated decisions;  
* easy and difficult states;  
* strategic opponents;  
* observable outcomes;  
* natural opportunities for memory and opponent modeling.

The goal is **not** to build the strongest poker bot. Poker is the testbed and UI for resource-aware reasoning.

---

## **Minimal reasoning router**

For each poker decision:

### **1\. Cheap pass**

Ask the model for:

* intended action;  
* confidence or uncertainty;  
* a very short rationale;  
* whether it believes additional reasoning is useful.

No expensive reasoning yet.

### **2\. Cheap perturbation test**

Generate a few nearby views of the same state. Examples:

* slightly rephrase the game description;  
* reorder irrelevant state fields;  
* hide or alter nonessential wording;  
* ask for the decision from a slightly different framing;  
* take two or three cheap stochastic samples.

Compare the resulting actions.

A very stable state might look like:

RAISE  
RAISE  
RAISE  
RAISE

An unstable state might look like:

CALL  
FOLD  
CALL  
RAISE

The latter is a candidate for deeper reasoning.

### **3\. Router**

Combine simple signals such as:

* action disagreement;  
* confidence;  
* size of the pot / consequence of the decision;  
* recent opponent behavior;  
* remaining inference budget.

The router chooses:

ACT

or:

PAY TO THINK

### **4\. Expensive pass**

If triggered, invoke the stronger reasoning mode with the richer context and strategy memory.

Charge the agent's inference bankroll and allow the deeper result to replace the initial action.

The UI should explicitly show cases such as:

Initial decision: FOLD

Perturbation stability: LOW  
Reasoning cost: 8.2K tokens

PAY TO THINK

Revised decision: CALL

This is the main demo moment.

---

## **Autonomous strategy is the stronger version**

We should avoid hard-coding poker strategy.

Give each agent:

* the game rules;  
* legal actions;  
* its observations;  
* a persistent private strategy notebook;  
* the objective of maximizing long-run resources.

After several hands, allow the agent to update its own notes:

Observed:  
Player B frequently raises after weak checks.

Current hypothesis:  
B may over-bluff late streets.

Adjustment:  
Consider calling B somewhat wider in large river pots.

This adds a second adaptive loop:

**play → observe → revise strategy → decide when to think → play again**

Starting several identical agents from the same initial prompt is particularly interesting. Different experiences may cause them to develop different strategies, reasoning habits, and opponent models without us assigning personalities.

That gives us an emergent multi-agent story almost for free.

---

## **Experiment we can finish in one day**

Compare three policies:

**Always Fast**  
Never purchases deeper reasoning.

**Always Think**  
Uses expensive reasoning on every meaningful decision.

**Pay-to-Think Agent**  
Uses cheap perturbation/stability signals to choose when deeper reasoning is worthwhile.

Track:

* game reward;  
* total inference tokens;  
* number of deep-reasoning calls;  
* fraction of decisions changed after deeper reasoning;  
* performance per inference budget;  
* examples where instability correctly predicted a useful reasoning intervention.

The most useful hackathon result does not need to be:

> “Adaptive routing wins poker.”

A much more achievable result is:

> **The adaptive agent recovers many of the decisions changed beneficially by deep reasoning while invoking it only on a minority of states.**

Even a handful of compelling live examples would be enough for the demo.

---

## **Connection to Perturbation Probing**

The conceptual bridge to our paper is worth making explicit:

**Perturbation Probing:**  
Use small interventions to reveal behaviorally important internal sensitivity.

**Pay-to-Think:**  
Use small interventions to reveal decision sensitivity before allocating expensive inference.

Both follow the same intuition:

> **Sensitivity is information.**

A stable response suggests that spending additional intervention or compute may have limited value. A fragile response indicates an interesting boundary worth examining more closely.

For the hackathon we should keep this connection lightweight. We do not need activation hooks, gradients, or model internals. The interesting research extension afterward would be to ask whether **internal perturbation signals outperform purely output-level disagreement as predictors of when additional reasoning helps**.

That could turn the hackathon prototype into a natural follow-up experiment for Perturbation Probing.

---

## **Demo framing**

A concise pitch:

> **Models are getting better at thinking longer, but they are still bad at knowing when thinking longer is worth the cost.**

> We built agents that have to pay for intelligence. They first make a cheap decision, probe how fragile that decision is, and only buy deeper reasoning when the situation appears unstable or important.

> Texas Hold’em gives us a live laboratory where the model must manage uncertainty, strategy, memory, and its own inference budget.