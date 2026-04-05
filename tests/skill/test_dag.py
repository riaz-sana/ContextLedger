"""Tests for DAG executor.

The DAG executor runs synthesis nodes in dependency order,
passing outputs between nodes.

Task: TASK-007 — Implement DAG executor
"""

import pytest


class TestDAGExecution:
    """Test execution of synthesis DAGs."""

    def test_execute_single_node(self):
        """Should execute a DAG with a single root node."""
        from contextledger.skill.dag import DAGExecutor
        executor = DAGExecutor()
        dag = {
            "nodes": [
                {"id": "extract", "type": "extraction", "depends_on": []},
            ]
        }
        results = executor.execute(dag, context={"input": "test data"})
        assert "extract" in results

    def test_execute_linear_chain(self):
        """Should execute nodes in dependency order (A -> B -> C)."""
        from contextledger.skill.dag import DAGExecutor
        executor = DAGExecutor()
        dag = {
            "nodes": [
                {"id": "a", "type": "extraction", "depends_on": []},
                {"id": "b", "type": "reasoning", "depends_on": ["a"]},
                {"id": "c", "type": "synthesis", "depends_on": ["b"]},
            ]
        }
        execution_order = []
        results = executor.execute(dag, context={}, on_node=lambda n: execution_order.append(n))
        assert execution_order == ["a", "b", "c"]

    def test_execute_parallel_roots(self):
        """Nodes with no dependencies can execute independently."""
        from contextledger.skill.dag import DAGExecutor
        executor = DAGExecutor()
        dag = {
            "nodes": [
                {"id": "a", "type": "extraction", "depends_on": []},
                {"id": "b", "type": "extraction", "depends_on": []},
                {"id": "c", "type": "synthesis", "depends_on": ["a", "b"]},
            ]
        }
        results = executor.execute(dag, context={})
        assert "a" in results
        assert "b" in results
        assert "c" in results

    def test_execute_passes_outputs_downstream(self):
        """Node outputs should be available as inputs to dependent nodes."""
        from contextledger.skill.dag import DAGExecutor
        executor = DAGExecutor()
        dag = {
            "nodes": [
                {"id": "extract", "type": "extraction", "depends_on": []},
                {"id": "synthesize", "type": "synthesis", "depends_on": ["extract"]},
            ]
        }
        results = executor.execute(dag, context={"input": "raw data"})
        # synthesize should have received extract's output
        assert results["synthesize"] is not None

    def test_execute_diamond_dependency(self):
        """Should handle diamond dependencies (A -> B, A -> C, B+C -> D)."""
        from contextledger.skill.dag import DAGExecutor
        executor = DAGExecutor()
        dag = {
            "nodes": [
                {"id": "a", "type": "extraction", "depends_on": []},
                {"id": "b", "type": "reasoning", "depends_on": ["a"]},
                {"id": "c", "type": "reasoning", "depends_on": ["a"]},
                {"id": "d", "type": "synthesis", "depends_on": ["b", "c"]},
            ]
        }
        results = executor.execute(dag, context={})
        assert "d" in results

    def test_execute_empty_dag(self):
        """Empty DAG should return empty results."""
        from contextledger.skill.dag import DAGExecutor
        executor = DAGExecutor()
        results = executor.execute({"nodes": []}, context={})
        assert results == {}

    def test_node_types_validated(self):
        """Only valid node types should be accepted: extraction, reasoning, synthesis, filter."""
        from contextledger.skill.dag import DAGExecutor
        executor = DAGExecutor()
        dag = {
            "nodes": [
                {"id": "bad", "type": "invalid_type", "depends_on": []},
            ]
        }
        with pytest.raises(ValueError):
            executor.execute(dag, context={})


class TestDAGTopologicalSort:
    """Test that the executor produces a valid topological order."""

    def test_topological_sort_linear(self):
        """Linear DAG should sort in dependency order."""
        from contextledger.skill.dag import DAGExecutor
        executor = DAGExecutor()
        dag = {
            "nodes": [
                {"id": "c", "type": "synthesis", "depends_on": ["b"]},
                {"id": "a", "type": "extraction", "depends_on": []},
                {"id": "b", "type": "reasoning", "depends_on": ["a"]},
            ]
        }
        order = executor.topological_sort(dag)
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_topological_sort_detects_cycle(self):
        """Cyclic DAG should raise an error."""
        from contextledger.skill.dag import DAGExecutor
        executor = DAGExecutor()
        dag = {
            "nodes": [
                {"id": "a", "type": "extraction", "depends_on": ["b"]},
                {"id": "b", "type": "reasoning", "depends_on": ["a"]},
            ]
        }
        with pytest.raises(ValueError):
            executor.topological_sort(dag)
