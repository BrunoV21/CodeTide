from codetide.agents.tide.utils import parse_patch_blocks

def test_single_patch_block():
    text = (
        "Some intro\n"
        "*** Begin Patch\n"
        "patch content 1\n"
        "*** End Patch\n"
        "Some outro"
    )
    result = parse_patch_blocks(text, multiple=False)
    assert result == "*** Begin Patch\npatch content 1\n*** End Patch"

def test_multiple_patch_blocks():
    text = (
        "*** Begin Patch\n"
        "patch content 1\n"
        "*** End Patch\n"
        "irrelevant\n"
        "*** Begin Patch\n"
        "patch content 2\n"
        "*** End Patch\n"
    )
    result = parse_patch_blocks(text, multiple=True)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == "*** Begin Patch\npatch content 1\n*** End Patch"
    assert result[1] == "*** Begin Patch\npatch content 2\n*** End Patch"

def test_no_patch_block_returns_none():
    text = "No patch markers here"
    assert parse_patch_blocks(text, multiple=True) is None
    assert parse_patch_blocks(text, multiple=False) is None

def test_patch_block_with_indentation_is_ignored():
    text = (
        "  *** Begin Patch\n"
        "indented patch\n"
        "*** End Patch\n"
        "*** Begin Patch\n"
        "valid patch\n"
        "*** End Patch\n"
    )
    result = parse_patch_blocks(text, multiple=True)
    assert len(result) == 1
    assert result[0] == "*** Begin Patch\nvalid patch\n*** End Patch"

def test_patch_block_at_start_and_end():
    text = (
        "*** Begin Patch\n"
        "start patch\n"
        "*** End Patch\n"
        "middle\n"
        "*** Begin Patch\n"
        "end patch\n"
        "*** End Patch"
    )
    result = parse_patch_blocks(text, multiple=True)
    assert len(result) == 2
    assert result[0] == "*** Begin Patch\nstart patch\n*** End Patch"
    assert result[1] == "*** Begin Patch\nend patch\n*** End Patch"

def test_patch_block_with_extra_content_inside():
    text = (
        "*** Begin Patch\n"
        "line1\n"
        "line2\n"
        "*** End Patch\n"
    )
    result = parse_patch_blocks(text, multiple=False)
    assert result == "*** Begin Patch\nline1\nline2\n*** End Patch"
