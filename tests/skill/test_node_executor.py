"""Tests for NodeExecutor with LLM-backed node handlers.

Task: TASK-028 — Wire LLM into DAG node handlers
"""

import pytest

from contextledger.skill.dag import DAGExecutor, NodeExecutor
from contextledger.backends.llm.stub import StubLLMClient


class TestNodeExecutor:
    def setup_method(self):
        self.llm = StubLLMClient()
        self.executor = NodeExecutor(self.llm)

    def test_extraction_node_calls_llm(self):
        node = {"id": "extract", "type": "extraction", "depends_on": []}
        profile = {"extraction": {"entities": ["finding"], "rules": []}}
        result = self.executor.execute(node, {"raw_content": "test data"}, profile)
        assert "entities" in result
        assert len(result["entities"]) > 0

    def test_reasoning_node_receives_entities(self):
        node = {"id": "reason", "type": "reasoning", "depends_on": []}
        profile = {"memory_schema": {"graph_nodes": ["Entity"]}}
        result = self.executor.execute(
            node, {"entities": [{"type": "table", "value": "users"}]}, profile
        )
        assert "relationships" in result

    def test_synthesis_node_renders_template(self):
        node = {"id": "synth", "type": "synthesis", "template": "t1", "depends_on": []}
        profile = {
            "synthesis": {
                "templates": [{"id": "t1", "prompt": "Find patterns in {entities}"}]
            }
        }
        result = self.executor.execute(node, {"entities": []}, profile)
        assert "findings" in result

    def test_synthesis_node_raises_on_missing_template(self):
        node = {"id": "synth", "type": "synthesis", "template": "nonexistent", "depends_on": []}
        profile = {"synthesis": {"templates": []}}
        with pytest.raises(ValueError, match="nonexistent"):
            self.executor.execute(node, {}, profile)

    def test_filter_node_applies_threshold(self):
        node = {"id": "filt", "type": "filter", "confidence_threshold": 0.8, "depends_on": []}
        findings = [
            {"content": "high", "confidence": 0.9},
            {"content": "low", "confidence": 0.3},
            {"content": "mid", "confidence": 0.8},
        ]
        result = self.executor.execute(node, {"findings": findings}, {})
        assert len(result["filtered_findings"]) == 2
        assert result["dropped"] == 1

    def test_filter_node_default_threshold(self):
        node = {"id": "filt", "type": "filter", "depends_on": []}
        findings = [{"content": "a", "confidence": 0.6}]
        result = self.executor.execute(node, {"findings": findings}, {})
        assert len(result["filtered_findings"]) == 1

    def test_unknown_type_raises(self):
        node = {"id": "bad", "type": "invalid", "depends_on": []}
        with pytest.raises(ValueError):
            self.executor.execute(node, {}, {})


class TestDAGExecutorWithNodeExecutor:
    def test_full_dag_with_stub_llm(self):
        llm = StubLLMClient()
        executor = DAGExecutor(node_executor=NodeExecutor(llm))
        dag = {
            "nodes": [
                {"id": "extract", "type": "extraction", "depends_on": []},
                {"id": "reason", "type": "reasoning", "depends_on": ["extract"]},
                {"id": "synth", "type": "synthesis", "template": "t1", "depends_on": ["reason"]},
            ]
        }
        profile = {
            "extraction": {"entities": ["finding"], "rules": []},
            "memory_schema": {"graph_nodes": ["Entity"]},
            "synthesis": {
                "templates": [{"id": "t1", "prompt": "Analyze {entities} and find patterns"}]
            },
        }
        results = executor.execute(dag, context={"raw_content": "test"}, profile=profile)
        assert "extract" in results
        assert "reason" in results
        assert "synth" in results
        assert "entities" in results["extract"]
        assert "findings" in results["synth"]

    def test_backward_compatible_without_executor(self):
        """DAGExecutor without node_executor should produce stub dicts."""
        executor = DAGExecutor()
        dag = {
            "nodes": [
                {"id": "a", "type": "extraction", "depends_on": []},
            ]
        }
        results = executor.execute(dag, context={"input": "test"})
        assert "a" in results
        assert results["a"]["node_id"] == "a"

    def test_backward_compatible_without_profile(self):
        """DAGExecutor with node_executor but no profile should produce stub dicts."""
        llm = StubLLMClient()
        executor = DAGExecutor(node_executor=NodeExecutor(llm))
        dag = {
            "nodes": [
                {"id": "a", "type": "extraction", "depends_on": []},
            ]
        }
        # profile=None means fallback to stub output
        results = executor.execute(dag, context={})
        assert results["a"]["node_id"] == "a"
