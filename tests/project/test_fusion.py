"""Tests for ContextFuser.

Task: TASK-032 — Implement context fusion
"""

import pytest

from contextledger.project.fusion import ContextFuser


class TestContextFuser:
    def test_fuse_single_skill_no_dedup(self):
        fuser = ContextFuser()
        results_by_skill = {
            "skill-a": [
                {"id": "1", "content": "Finding one", "metadata": {}},
                {"id": "2", "content": "Finding two", "metadata": {}},
            ]
        }
        result = fuser.fuse("test query", results_by_skill)
        assert len(result.fused_results) == 2

    def test_fuse_multi_skill_dedup_same_content(self):
        fuser = ContextFuser()
        results_by_skill = {
            "skill-a": [{"id": "1", "content": "Shared finding", "metadata": {}}],
            "skill-b": [{"id": "2", "content": "Shared finding", "metadata": {}}],
        }
        result = fuser.fuse("query", results_by_skill)
        assert len(result.fused_results) == 1

    def test_fuse_multi_skill_attribution_preserved(self):
        fuser = ContextFuser()
        results_by_skill = {
            "skill-a": [{"id": "1", "content": "Shared finding", "metadata": {}}],
            "skill-b": [{"id": "2", "content": "Shared finding", "metadata": {}}],
        }
        result = fuser.fuse("query", results_by_skill)
        meta = result.fused_results[0].get("metadata", {})
        assert "skill-a" in meta["source_skills"]
        assert "skill-b" in meta["source_skills"]

    def test_fuse_cross_skill_flag(self):
        fuser = ContextFuser()
        results_by_skill = {
            "a": [{"id": "1", "content": "shared", "metadata": {}}],
            "b": [{"id": "2", "content": "shared", "metadata": {}}],
        }
        result = fuser.fuse("q", results_by_skill)
        assert result.fused_results[0]["metadata"]["cross_skill"] is True

    def test_fuse_active_skill_ranked_first(self):
        fuser = ContextFuser()
        results_by_skill = {
            "a": [{"id": "1", "content": "from a - short", "metadata": {}}],
            "b": [{"id": "2", "content": "from b - this is a much longer finding with more content", "metadata": {}}],
        }
        result = fuser.fuse("q", results_by_skill, active_skill="a")
        # Active skill's result should be first despite being shorter
        first_sources = result.fused_results[0]["metadata"]["source_skills"]
        assert "a" in first_sources

    def test_fuse_empty_results(self):
        fuser = ContextFuser()
        result = fuser.fuse("q", {})
        assert result.fused_results == []
        assert result.query == "q"

    def test_fuse_preserves_query_and_reason(self):
        fuser = ContextFuser()
        result = fuser.fuse("my query", {}, active_skill="x", routing_reason="test reason")
        assert result.query == "my query"
        assert result.active_skill == "x"
        assert result.routing_reason == "test reason"

    def test_fuse_unique_findings_not_deduped(self):
        fuser = ContextFuser()
        results_by_skill = {
            "a": [{"id": "1", "content": "Unique A finding", "metadata": {}}],
            "b": [{"id": "2", "content": "Unique B finding", "metadata": {}}],
        }
        result = fuser.fuse("q", results_by_skill)
        assert len(result.fused_results) == 2
