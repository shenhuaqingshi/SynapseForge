import pytest
from synapseforge.core.ast_parser import BlockType, MarkdownASTParser, slugify


def test_slugify():
    assert slugify("Section 1: Theoretical Foundations") == "section-1-theoretical-foundations"
    assert slugify("理论基石 与 形式化建模") == "理论基石-与-形式化建模"


def test_parse_blocks_simple():
    text = """# Heading 1
This is a paragraph with some content.

```python
def foo():
    return 42
```

| Header 1 | Header 2 |
|---|---|
| Cell 1 | Cell 2 |

> Important quote block.
"""
    blocks = MarkdownASTParser.parse_blocks(text)
    types = [b.type for b in blocks]
    assert types == [
        BlockType.HEADING,
        BlockType.PARAGRAPH,
        BlockType.CODE_BLOCK,
        BlockType.TABLE,
        BlockType.BLOCKQUOTE,
    ]
    assert blocks[0].title == "Heading 1"
    assert blocks[0].level == 1
    assert blocks[2].metadata["lang"] == "python"


def test_extract_citations():
    text = "As shown by @vaswani2017attention and verified in @lamport1982byzantine, also see [^custom_ref]."
    cites = MarkdownASTParser.extract_citations(text)
    assert "vaswani2017attention" in cites
    assert "lamport1982byzantine" in cites
    assert "custom_ref" in cites


def test_parse_sections():
    text = """# Chapter 1
Content 1.

## Chapter 1.1
Content 1.1.

# Chapter 2
Content 2.
"""
    sections = MarkdownASTParser.parse_sections(text)
    assert len(sections) == 3
    assert sections[0].title == "Chapter 1"
    assert sections[1].title == "Chapter 1.1"
    assert sections[2].title == "Chapter 2"
