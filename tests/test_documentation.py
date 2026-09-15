import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_bilingual_operator_guides_cover_the_required_safe_workflow(self):
        requirements = {
            "README.md": (
                "Settings → Account & Security → Account Security → Third-party client login security management → Generate new password", "separate secure PowerShell window",
                "Luna", "low reasoning", "Terra", "humanizer", "Sol", "high reasoning", "Bcc", "never sends automatically",
            ),
            "README.zh-CN.md": (
                "设置 → 账户与安全 → 账户安全 → 三方客户端登录安全管理 → 生成新密码", "独立的安全 PowerShell 窗口",
                "Luna", "低推理", "Terra", "humanizer", "Sol", "高推理", "密送", "绝不自动发送",
            ),
            "INSTALL.md": (
                "Settings → Account & Security → Account Security → Third-party client login security management → Generate new password", "separate secure PowerShell window", "integrated terminal is never a password fallback",
                "shown only once", "Codex chat", "hidden local prompt", "Luna", "low reasoning", "Terra", "Bcc", "never sends automatically",
            ),
            "INSTALL.zh-CN.md": (
                "设置 → 账户与安全 → 账户安全 → 三方客户端登录安全管理 → 生成新密码", "独立的安全 PowerShell 窗口", "集成终端绝不会作为密码输入的后备方式",
                "只显示一次", "Codex 对话", "本地隐藏输入", "Luna", "低推理", "Terra", "密送", "绝不自动发送",
            ),
            "TROUBLESHOOTING.md": (
                "third-party client password", "does not prove", "administrator", "Luna", "low reasoning", "Terra", "humanizer", "Bcc", "automatic send",
            ),
            "TROUBLESHOOTING.zh-CN.md": (
                "第三方客户端安全密码", "不等于", "管理员", "Luna", "低推理", "Terra", "humanizer", "密送", "自动发送",
            ),
        }
        for filename, phrases in requirements.items():
            document = (ROOT / filename).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(phrase, document)

    def test_project_instructions_and_each_skill_define_safe_boundaries(self):
        files = [ROOT / "AGENTS.md"] + sorted((ROOT / ".agents" / "skills").glob("*/SKILL.md"))
        self.assertEqual(len(files), 9)
        for path in files:
            content = path.read_text(encoding="utf-8").lower()
            for required in ("purpose", "permitted", "failure", "approval"):
                with self.subTest(path=path, required=required):
                    self.assertIn(required, content)

    def test_installation_instructions_require_the_windows_secure_window_path(self):
        for path in (
            ROOT / "AGENTS.md",
            ROOT / ".agents" / "skills" / "business-email-management" / "SKILL.md",
        ):
            content = path.read_text(encoding="utf-8")
            for required in ("--secure-window", "--workspace", "--daily-brief"):
                with self.subTest(path=path, required=required):
                    self.assertIn(required, content)

    def test_humanizer_skill_explicitly_preserves_business_facts_and_recipients(self):
        content = (ROOT / ".agents" / "skills" / "humanizer" / "SKILL.md").read_text(encoding="utf-8").lower()
        for protected_value in ("facts", "money", "dates", "commitments", "recipients", "language"):
            with self.subTest(protected_value=protected_value):
                self.assertIn(protected_value, content)

    def test_legacy_skill_name_and_bilingual_upgrade_guides_are_shipped(self):
        legacy = ROOT / ".agents" / "skills" / "business-email-managerment" / "SKILL.md"
        self.assertTrue(legacy.is_file())
        self.assertIn("business-email-management", legacy.read_text(encoding="utf-8"))
        self.assertIn("business-email-managerment", (ROOT / "UPGRADE.md").read_text(encoding="utf-8"))
        self.assertIn("business-email-managerment", (ROOT / "UPGRADE.zh-CN.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
