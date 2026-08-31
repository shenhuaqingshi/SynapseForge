import pytest
from pathlib import Path
from synapseforge.security.redactor import ConfidentialityRedactor
from synapseforge.security.crypto_vault import CryptoVault
from synapseforge.security.acl import NodeAccessController


def test_confidentiality_redactor_scanning(tmp_path):
    redactor = ConfidentialityRedactor(workspace_root=tmp_path)
    redactor.add_classified_term("Project-Apollo-Stealth")

    sample_text = """
# Internal Architecture
Deploy key: sk-ant-api03-abcdef1234567890abcdef12
Contact: 13800138000
Classified initiative: Project-Apollo-Stealth is active.
"""
    issues = redactor.scan_for_secrets(sample_text)
    assert len(issues) >= 2

    # Test two-way redaction
    sanitized, token_map = redactor.redact(sample_text)
    assert "sk-ant" not in sanitized
    assert "13800138000" not in sanitized
    assert "Project-Apollo-Stealth" not in sanitized
    assert len(token_map) >= 2

    # Test local rehydration
    restored = redactor.unredact(sanitized, token_map)
    assert restored == sample_text


def test_crypto_vault_encryption_and_decryption(tmp_path):
    crypto = CryptoVault()
    secret_text = "# Proprietary Quantum Algorithm\nTheorem 1: S |psi> = e^{i theta} |psi>"
    passphrase = "UltraSecureKey2026!#"

    # Encrypt
    encrypted_bundle = crypto.encrypt_content(secret_text, passphrase)
    assert encrypted_bundle["ciphertext"] != secret_text
    assert "tag" in encrypted_bundle

    # Decrypt
    decrypted = crypto.decrypt_content(encrypted_bundle, passphrase)
    assert decrypted == secret_text

    # Wrong passphrase must fail
    with pytest.raises(ValueError):
        crypto.decrypt_content(encrypted_bundle, "WrongPassphrase123")


def test_node_access_controller_token_verification(tmp_path):
    acl = NodeAccessController(workspace_root=tmp_path)
    res = acl.generate_token(room_id="room-consensus-01", node_id="node-mac-01", role="drafter")
    assert res["ok"] is True
    token = res["token"]

    # Verify valid token
    ver = acl.verify_token(token)
    assert ver["valid"] is True
    assert ver["payload"]["room_id"] == "room-consensus-01"
    assert ver["payload"]["node_id"] == "node-mac-01"

    # Tampered token must fail
    tampered_token = token[:-4] + "AAAA"
    bad_ver = acl.verify_token(tampered_token)
    assert bad_ver["valid"] is False
