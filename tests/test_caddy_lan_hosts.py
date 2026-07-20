import os
import sys
import unittest


root_folder = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + os.sep + "..")
if root_folder not in sys.path:
    sys.path.append(root_folder)

from scripts.prod import update_caddy_lan_hosts


class TestCaddyLanHosts(unittest.TestCase):
    def test_build_caddyfile_includes_multiple_lan_hosts(self):
        content = update_caddy_lan_hosts.build_caddyfile(["192.168.1.99", "10.181.130.24"], "127.0.0.1:9741")

        self.assertIn("http://192.168.1.99, http://10.181.130.24", content)
        self.assertIn("https://192.168.1.99, https://10.181.130.24", content)
        self.assertIn("reverse_proxy 127.0.0.1:9741", content)
        self.assertIn("handle /api/pocket/v1/*", content)

    def test_collect_lan_hosts_keeps_private_addresses_only(self):
        original = update_caddy_lan_hosts._active_windows_ipv4_addresses
        try:
            update_caddy_lan_hosts._active_windows_ipv4_addresses = lambda: [
                "10.181.130.24",
                "169.254.1.1",
                "127.0.0.1",
                "8.8.8.8",
            ]

            hosts = update_caddy_lan_hosts.collect_lan_hosts(["192.168.1.99", "172.16.2.3"])
        finally:
            update_caddy_lan_hosts._active_windows_ipv4_addresses = original

        self.assertEqual(hosts, ["192.168.1.99", "172.16.2.3", "10.181.130.24"])


if __name__ == "__main__":
    unittest.main()
