import pytest
from synapseforge.core.conflict_resolver import SemanticConflictResolver


def test_merge_clean_addition():
    base = """# Section 1
Original content of section 1.
"""
    ours = """# Section 1
Original content of section 1.

# Section 2
New section added in branch by Drafter Agent.
"""
    theirs = """# Section 1
Original content of section 1.
"""
    resolver = SemanticConflictResolver()
    res = resolver.merge_texts(base, ours, theirs)
    assert not res.has_conflicts
    assert "Section 2" in res.merged_content
    assert "New section added in branch" in res.merged_content


def test_merge_independent_section_edits():
    base = """# Section 1
Base content 1.

# Section 2
Base content 2.
"""
    ours = """# Section 1
Modified content 1 by Agent A.

# Section 2
Base content 2.
"""
    theirs = """# Section 1
Base content 1.

# Section 2
Modified content 2 by Human Reviewer.
"""
    resolver = SemanticConflictResolver()
    res = resolver.merge_texts(base, ours, theirs)
    assert not res.has_conflicts
    assert "Modified content 1 by Agent A" in res.merged_content
    assert "Modified content 2 by Human Reviewer" in res.merged_content


def test_merge_conflicting_edits():
    base = """# Section 1
Base content.
"""
    ours = """# Section 1
Modified by Agent with contradictory hypothesis X.
"""
    theirs = """# Section 1
Modified by Human with contradictory hypothesis Y.
"""
    resolver = SemanticConflictResolver()
    res = resolver.merge_texts(base, ours, theirs)
    assert res.has_conflicts
    assert res.conflict_count == 1
    assert "<<<<<<< OURS" in res.merged_content
    assert "=======" in res.merged_content
    assert ">>>>>>> THEIRS" in res.merged_content
