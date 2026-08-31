import pytest
from pathlib import Path
from synapseforge.core.user_prompts import UserPromptManager


def test_user_prompt_manager_lifecycle(tmp_path):
    mgr = UserPromptManager(workspace_root=tmp_path)
    
    # 1. User sets a custom prompt
    custom_text = "# Role: Senior Cryptographer\n\nMust use rigorous sigma-algebra notation."
    res = mgr.set_prompt(
        role_id="crypto_expert",
        prompt_content=custom_text,
        display_name="密码学专家",
        description="专门负责零知识证明与加密拓扑推导",
        model="deepseek-reasoner"
    )
    assert res["ok"] is True
    assert res["role_id"] == "crypto_expert"
    assert (tmp_path / "prompts" / "crypto_expert.md").exists()

    # 2. User gets the prompt
    fetched = mgr.get_prompt("crypto_expert")
    assert fetched == custom_text

    # 3. User lists prompts
    prompts = mgr.list_prompts()
    assert len(prompts) == 1
    assert prompts[0]["role_id"] == "crypto_expert"
    assert prompts[0]["display_name"] == "密码学专家"

    # 4. User deletes the prompt
    deleted = mgr.delete_prompt("crypto_expert")
    assert deleted is True
    assert not (tmp_path / "prompts" / "crypto_expert.md").exists()
    assert len(mgr.list_prompts()) == 0
