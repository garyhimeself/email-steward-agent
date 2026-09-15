import socket
import ssl
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


from email_steward.preflight import LocalNetworkPreflight, run_local_network_preflight


class LocalNetworkPreflightTests(unittest.TestCase):
    def test_reports_local_network_without_credentials_or_imap_login(self):
        calls = []

        result = run_local_network_preflight(
            hostname_fn=lambda: "operator-laptop",
            resolver=lambda host, port: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.10", port)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.11", port)),
            ],
            tls_probe=lambda host, port: calls.append((host, port)) or True,
            public_ip_fetcher=lambda: "198.51.100.8",
        )

        self.assertEqual(result.hostname, "operator-laptop")
        self.assertEqual(result.imap_host, "imap.qiye.aliyun.com")
        self.assertEqual(result.imap_port, 993)
        self.assertEqual(result.dns_addresses, ("203.0.113.10", "203.0.113.11"))
        self.assertTrue(result.tls_connected)
        self.assertEqual(result.public_ip, "198.51.100.8")
        self.assertEqual(calls, [("imap.qiye.aliyun.com", 993)])

    def test_public_ip_failure_is_reported_as_unknown_without_failing_preflight(self):
        result = run_local_network_preflight(
            hostname_fn=lambda: "operator-laptop",
            resolver=lambda host, port: [],
            tls_probe=lambda host, port: False,
            public_ip_fetcher=lambda: (_ for _ in ()).throw(TimeoutError("no service")),
        )

        self.assertEqual(result.public_ip, "unknown")
        self.assertFalse(result.tls_connected)
        self.assertEqual(result.dns_addresses, ())

    def test_tls_probe_uses_a_verified_context_and_bounded_timeout(self):
        contexts = []
        sockets = []

        class FakeRawSocket:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class FakeTlsSocket:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class FakeContext:
            check_hostname = True
            verify_mode = ssl.CERT_REQUIRED

            def wrap_socket(self, raw_socket, server_hostname):
                sockets.append((raw_socket, server_hostname))
                return FakeTlsSocket()

        def context_factory():
            context = FakeContext()
            contexts.append(context)
            return context

        from email_steward.preflight import probe_tls

        self.assertTrue(
            probe_tls(
                "imap.qiye.aliyun.com",
                993,
                socket_factory=lambda address, timeout: FakeRawSocket(),
                context_factory=context_factory,
            )
        )
        self.assertEqual(len(contexts), 1)
        self.assertTrue(contexts[0].check_hostname)
        self.assertEqual(contexts[0].verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(sockets[0][1], "imap.qiye.aliyun.com")

    def test_installer_runs_preflight_before_any_setup_prompt_and_supports_preflight_only_mode(self):
        from installer.install_agent import main

        messages = []
        install_calls = []
        observation = LocalNetworkPreflight(
            hostname="operator-laptop",
            imap_host="imap.qiye.aliyun.com",
            imap_port=993,
            dns_addresses=("203.0.113.10",),
            tls_connected=True,
            public_ip="198.51.100.8",
        )

        exit_code = main(
            ["--preflight"],
            preflight_runner=lambda: observation,
            output_fn=messages.append,
            install_fn=lambda *args, **kwargs: install_calls.append(kwargs),
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(install_calls, [])
        self.assertIn("Current public IP: 198.51.100.8", messages)
        self.assertTrue(any("not a promise of a fixed IP" in message for message in messages))

        messages.clear()
        main(
            ["--name", "Wade", "--email", "wade@example.com"],
            preflight_runner=lambda: observation,
            output_fn=messages.append,
            install_fn=lambda *args, **kwargs: install_calls.append(kwargs),
        )
        self.assertEqual(len(install_calls), 1)
        self.assertEqual(install_calls[0]["profile_prefill"]["email"], "wade@example.com")
        self.assertLess(messages.index("Current public IP: 198.51.100.8"), len(messages))

    def test_windows_launcher_uses_utf8_for_bilingual_preflight_output(self):
        launcher = (
            Path(__file__).resolve().parents[1] / "installer" / "install_agent.bat"
        ).read_text(encoding="utf-8")

        self.assertIn("chcp 65001", launcher)


if __name__ == "__main__":
    unittest.main()
