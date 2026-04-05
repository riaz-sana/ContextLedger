# ContextLedger — Remaining Work & README Fixes

**For Claude Code. Complete these before or alongside the Phase 2 project manifest work.**
**Ordered by priority — do not skip.**

---

## Part 1: Critical Gap — Wire LLM into DAG Node Handlers

This must be done first. Without it, Tier 2 conflict resolution (the key differentiator) does not work, and the README claim about semantic evaluation is false.

### What's broken

`skill/dag.py` has four node types — `extraction`, `reasoning`, `synthesis`, `filter` — that return stub outputs. The executor handles topological ordering and dependency passing correctly, but no node type actually calls an LLM.

Tier 2 evaluation in `merge/evaluator.py` is structurally correct but runs against stub outputs. The result: scoring is synthetic, not real. The differentiator does not hold.

### What to implement

**Add to `core/protocols.py`:**

```python
class LLMClient(Protocol):
    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        """Send a completion request. Returns response text."""
        ...
```

**New file `backends/llm/claude.py`:**

```python
import anthropic

class ClaudeLLMClient:
    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
```

**New file `backends/llm/stub.py`:**

```python
class StubLLMClient:
    """Returns deterministic stub outputs. Used in tests only."""
    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        return '{"findings": [{"content": "stub finding", "confidence": 0.8}]}'
```

**Update `skill/dag.py` — add NodeExecutor with real handlers:**

```python
class NodeExecutor:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def execute(self, node, inputs, profile):
        handlers = {
            "extraction": self._handle_extraction,
            "reasoning": self._handle_reasoning,
            "synthesis": self._handle_synthesis,
            "filter": self._handle_filter,
        }
        handler = handlers.get(node["type"])
        if not handler:
            raise ValueError(f"Unknown node type: {node['type']}")
        return handler(node, inputs, profile)

    def _handle_extraction(self, node, inputs, profile):
        """
        Extract entities from raw session content.
        Calls LLM with extraction prompt derived from profile.extraction.rules.
        Returns: {"entities": [...], "confidence_scores": {...}}
        """
        entity_types = profile.get("extraction", {}).get("entities", [])
        extraction_rules = profile.get("extraction", {}).get("rules", [])
        raw_content = inputs.get("raw_content", "")

        prompt = (
            f"Extract entities of types {entity_types} from the following content.\n"
            f"Rules: {extraction_rules}\n\n"
            f"Content:\n{raw_content}\n\n"
            f"Respond in JSON: {{\"entities\": [{{\"type\": ..., \"value\": ..., "
            f"\"confidence\": 0-1}}]}}"
        )
        response = self.llm_client.complete(prompt, max_tokens=1000)
        return self._parse_json_response(response, default={"entities": []})

    def _handle_reasoning(self, node, inputs, profile):
        """
        Build relationships between extracted entities.
        Input: entities from upstream extraction node.
        Returns: {"relationships": [...]}
        """
        entities = inputs.get("entities", [])
        graph_schema = profile.get("memory_schema", {})

        prompt = (
            f"Given these entities: {entities}\n"
            f"And this graph schema: {graph_schema}\n\n"
            f"Identify relationships between entities.\n"
            f"Respond in JSON: {{\"relationships\": [{{\"from\": ..., \"to\": ..., "
            f"\"label\": ...}}]}}"
        )
        response = self.llm_client.complete(prompt, max_tokens=1000)
        return self._parse_json_response(response, default={"relationships": []})

    def _handle_synthesis(self, node, inputs, profile):
        """
        Synthesise findings from entities and relationships.
        Looks up template by node['template'] in profile.synthesis.templates.
        Returns: {"findings": [...], "confidence": float}
        """
        template_id = node.get("template")
        templates = profile.get("synthesis", {}).get("templates", [])
        template = next((t for t in templates if t["id"] == template_id), None)

        if not template:
            raise ValueError(f"Template '{template_id}' not found in profile")

        # Substitute variables into template prompt
        prompt = template["prompt"].format(
            entities=inputs.get("entities", []),
            relationships=inputs.get("relationships", []),
            source=inputs.get("source", "unknown"),
        )
        response = self.llm_client.complete(prompt, max_tokens=1500)
        return self._parse_json_response(response, default={"findings": []})

    def _handle_filter(self, node, inputs, profile):
        """
        Filter findings by confidence threshold.
        Returns: {"filtered_findings": [...], "dropped": int}
        """
        findings = inputs.get("findings", [])
        threshold = node.get("confidence_threshold", 0.5)
        filtered = [f for f in findings if f.get("confidence", 1.0) >= threshold]
        return {"filtered_findings": filtered, "dropped": len(findings) - len(filtered)}

    def _parse_json_response(self, response: str, default: dict) -> dict:
        import json
        try:
            clean = response.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except Exception:
            return default
```

**Update DAGExecutor in `skill/dag.py`** to accept and use NodeExecutor:

```python
class DAGExecutor:
    def __init__(self, node_executor=None):
        # If no executor provided, use stub (backward compatible)
        self.node_executor = node_executor or StubNodeExecutor()

    def execute(self, dag_config, initial_inputs, profile):
        """
        Execute DAG in topological order.
        Each node receives outputs from its dependencies as inputs.
        """
        nodes = dag_config.get("nodes", [])
        order = self._topological_sort(nodes)
        outputs = dict(initial_inputs)

        for node_id in order:
            node = next(n for n in nodes if n["id"] == node_id)
            node_inputs = self._collect_inputs(node, outputs)
            result = self.node_executor.execute(node, node_inputs, profile)
            outputs[node_id] = result

        return outputs
```

### Tests to add in `tests/skill/test_dag_executor.py`

```
- test_extraction_node_calls_llm_with_correct_prompt
- test_reasoning_node_receives_extraction_output_as_input
- test_synthesis_node_renders_template_correctly
- test_synthesis_node_raises_on_missing_template
- test_filter_node_applies_threshold
- test_full_dag_end_to_end_with_stub_llm
- test_full_dag_end_to_end_with_real_llm  (skip unless ANTHROPIC_API_KEY set)
- test_dag_executor_backward_compatible_with_no_executor_arg
```

### Estimated effort: ~0.5 day

---

## Part 2: Complete Tier 2 Evaluation Wiring

Now that DAG node handlers are real, wire them into `merge/evaluator.py` properly.

### What to update in `merge/evaluator.py`

Replace the stub template execution call with real NodeExecutor:

```python
def _run_template(self, template, findings, profile, llm_client):
    """
    Run a synthesis template against findings using the real DAG executor.
    Returns list of synthesised outputs.
    """
    from skill.dag import DAGExecutor, NodeExecutor
    executor = DAGExecutor(node_executor=NodeExecutor(llm_client))

    # Build a minimal single-node DAG for evaluation
    eval_dag = {
        "nodes": [
            {
                "id": "eval_synthesis",
                "type": "synthesis",
                "template": template["id"],
                "depends_on": [],
            }
        ]
    }
    inputs = {
        "entities": self._findings_to_entities(findings),
        "relationships": [],
        "source": "evaluation_harness",
    }
    result = executor.execute(eval_dag, inputs, profile)
    return result.get("eval_synthesis", {}).get("findings", [])
```

### Add LLM-as-judge scoring to `merge/scorer.py`

```python
def score_with_llm_judge(self, outputs_a, outputs_b, llm_client):
    """
    Use LLM-as-judge to compare two sets of synthesis outputs.
    Returns: {"winner": "a"|"b"|"tie", "confidence": float, "reasoning": str,
              "precision_a": float, "precision_b": float,
              "recall_a": float, "recall_b": float,
              "novelty_a": float, "novelty_b": float}
    """
    import json
    prompt = f"""You are evaluating two sets of findings extracted from the same source data.

Set A (parent profile version):
{json.dumps(outputs_a, indent=2)}

Set B (fork profile version):
{json.dumps(outputs_b, indent=2)}

Evaluate each set on three dimensions (score 0.0 to 1.0):
- Precision: are findings accurate and grounded in the source?
- Recall: do findings capture all important information?
- Novelty: does this set discover things the other misses?

Respond ONLY in JSON, no other text:
{{
  "winner": "a" or "b" or "tie",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "precision_a": 0.0-1.0,
  "precision_b": 0.0-1.0,
  "recall_a": 0.0-1.0,
  "recall_b": 0.0-1.0,
  "novelty_a": 0.0-1.0,
  "novelty_b": 0.0-1.0
}}"""

    response = llm_client.complete(prompt, max_tokens=500)
    try:
        clean = response.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception:
        return {
            "winner": "tie", "confidence": 0.0,
            "reasoning": "LLM judge parse failed",
            "precision_a": 0.5, "precision_b": 0.5,
            "recall_a": 0.5, "recall_b": 0.5,
            "novelty_a": 0.5, "novelty_b": 0.5,
        }
```

### Update `merge/resolver.py` Tier 2 flow

When Tier 2 triggers, the resolver should now:
1. Call `evaluator._run_template()` with real LLM client for both versions
2. Call `scorer.score_with_llm_judge()` for final verdict
3. Surface the full score breakdown to the user before asking for decision

```python
# In resolver.py, Tier 2 path:
def _evaluate_tier2(self, section_key, parent_value, fork_value, profile, llm_client):
    outputs_a = self.evaluator._run_template(parent_value, self.recent_findings, profile, llm_client)
    outputs_b = self.evaluator._run_template(fork_value, self.recent_findings, profile, llm_client)
    scores = self.scorer.score_with_llm_judge(outputs_a, outputs_b, llm_client)
    return {
        "conflict_type": "tier2",
        "section": section_key,
        "scores": scores,
        "recommendation": "merge" if scores["winner"] == "b" else "keep_parent",
        "requires_user_decision": True,
    }
```

### Tests to add in `tests/merge/test_evaluator_real.py`

```
- test_tier2_runs_real_template_with_stub_llm
- test_tier2_llm_judge_returns_winner
- test_tier2_scores_have_precision_recall_novelty
- test_tier2_parse_failure_returns_tie_gracefully
- test_tier2_recommendation_is_merge_or_keep_parent
- test_tier2_with_real_llm (skip unless ANTHROPIC_API_KEY set)
```

### Estimated effort: ~0.5 day (after Part 1)

---

## Part 3: README Corrections

Six targeted fixes. No code changes needed. Do these immediately.

### Fix 1 — Opening problem, remove domain specificity

**Find and replace this passage:**
```
You've built a skill — a workflow that extracts findings from a supervised database.
It works. Now you need to adapt it for filesystem documents. So you copy the files,
make changes...
```

**Replace with:**
```
You've built a workflow — extraction rules, reasoning logic, synthesis templates —
for one domain. You want to fork it for a different domain, iterate independently
on each, then merge improvements back without losing reproducibility.

This works for any workflow you model as a ContextLedger skill profile:

- Agent testing frameworks (fork rules per target type or environment)
- LLM cost analysis pipelines (fork detector rules per provider or use case)
- Data extraction workflows (fork parsing rules per data source)
- RAG systems (fork retrieval strategies per knowledge domain)
- Document processors (fork parsing rules per document type)
- Research workflows (fork analysis rules per research question)
```

### Fix 2 — "Semantic conflict resolution" claim

**Find:**
```
merge improvements back with semantic conflict resolution that understands whether
a change actually improves findings
```

**Replace with:**
```
merge improvements back with tier-based conflict resolution — auto-merge for
non-overlapping changes, LLM-evaluated scoring for overlapping synthesis changes
(requires ANTHROPIC_API_KEY), and explicit blocking for conflicting DAG dependencies
```

### Fix 3 — "Works for any workflow" claim

**Find:**
```
Works for any workflow with configurable extraction, reasoning, and synthesis steps
```

**Replace with:**
```
Works for any workflow you model as a skill profile — you define what to extract,
how to reason about it, and how to synthesise findings. ContextLedger versions,
forks, and merges that configuration.
```

### Fix 4 — "Semantic understanding layered on Git" — make it concrete

**Find (in Key Design Decisions):**
```
Git for versioning — don't reinvent it; add semantic understanding on top
```

**Replace with:**
```
Git for versioning — don't reinvent it; add semantic understanding on top.
Three concrete things this means: (1) section-aware diffing — profiles are compared
field by field (extraction.entities, synthesis.dag.nodes, memory_schema.graph_edges),
not as raw text; (2) DAG dependency analysis — if a merged change touches a node
that downstream nodes depend on, it's flagged as a conflict; (3) Tier 2 evaluation —
overlapping synthesis template changes are scored by running both versions against
real findings via LLM-as-judge
```

### Fix 5 — Current Status table, Tier 2 accuracy

**Find:**
```
| Conflict resolution (tier 1/2/3) | ✅ Ready |
| Evaluation harness (precision/recall/novelty) | ✅ Ready (stub scoring — full LLM integration in progress) |
```

**Replace with:**
```
| Conflict resolution tier 1 (auto-merge) | ✅ Ready |
| Conflict resolution tier 2 (LLM evaluation) | ⚠️ Structure ready; requires DAG LLM wiring (see remaining-work.md Part 1) |
| Conflict resolution tier 3 (block + manual) | ✅ Ready |
| Evaluation harness | ⚠️ Harness structure ready; LLM-backed scoring requires Part 1 |
```

### Fix 6 — GitHub repo description (fix manually on GitHub.com, not in code)

**Current:**
```
ContextLedger is a context layer and ctx versioning platform for research engineers
and developers working across multiple AI interfaces and domains.
```

**Replace with:**
```
ContextLedger is a skill versioning and context synthesis platform for AI engineers
working across multiple domains and interfaces.
```

---

## Part 4: Add Multi-Skill Section to README

Add this as a new section after "Mode 2: Second Brain". This documents Phase 2 functionality — add it when Phase 2 is implemented, not before.

```markdown
## Mode 3: Multi-Skill Projects

If your project has multiple distinct components — each with its own workflow,
terminology, and context — declare them all in a project manifest.
ContextLedger auto-routes queries to the right skill based on your working directory,
the file you're editing, or keywords in your query.

**Available after Phase 2 is implemented.**

### Setup

```bash
ctx project init
```

Or write `.contextledger/project.yaml` directly:

```yaml
name: my-project
version: 1.0.0

skills:
  - extraction-skill
  - analysis-skill
  - reporting-skill

default_skill: analysis-skill
fusion_enabled: true

routes:
  - skill: extraction-skill
    directories: [src/extractors/]
    keywords: [extract, parse, ingest]

  - skill: analysis-skill
    directories: [src/analysis/]
    keywords: [analyze, detect, score]

  - skill: reporting-skill
    directories: [src/reports/]
    keywords: [report, summary, output]
```

### Querying

```bash
# Auto-routes based on cwd + query keywords
ctx project query "how does entity extraction work"

# Query all skills simultaneously, returns fused results with attribution
ctx project query "what findings cross extraction and analysis" --all

# Override routing
ctx project query "detection thresholds" --profile analysis-skill

# Debug routing without running a query
ctx project route --query "retry waste detector"
# → "analysis-skill (keyword match: detector)"

# Project health
ctx project status
```

### When to use multi-skill vs single-skill

**Single-skill:** one domain, one workflow, or you're iterating via fork/merge.
**Multi-skill:** distinct components with different terminology, and you want context
from one to surface when querying another.
```

---

## Summary

| Part | What | Effort | Do when |
|---|---|---|---|
| Part 1 | Wire LLM into DAG node handlers | ~0.5 day | Immediately — blocks Tier 2 |
| Part 2 | Complete Tier 2 evaluation wiring | ~0.5 day | After Part 1 |
| Part 3 | 6 README corrections | ~1 hour | Immediately — no code needed |
| Part 4 | README multi-skill section | ~30 min | After Phase 2 is implemented |

**Parts 1 and 2 are the only things that make the key differentiator claim true.**
**Part 3 fixes things that are currently factually wrong in the README.**
**Part 4 is documentation-only, add it when the code exists.**

---

*Version 1.0. Companion document to contextledger-phase2-plan.md*
