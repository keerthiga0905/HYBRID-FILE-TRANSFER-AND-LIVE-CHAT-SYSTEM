"""
Unit tests for Packet Loss Simulation & Developer Diagnostics.
"""

import unittest
import time
import threading
from shared.config import DEFAULT_HOST
from server.udp_server import UDPServer
from client.client_controller import controller


class TestPacketLossSimulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_port = 6009
        cls.server = UDPServer(host=DEFAULT_HOST, port=cls.server_port)
        cls.server_thread = threading.Thread(target=cls.server.start, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_set_simulated_loss_rate(self):
        """Test setting simulated loss rate clamping and notification response."""
        res = controller.set_simulated_loss(0.20)
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("simulated_loss_rate"), 0.20)
        self.assertEqual(res.get("loss_percentage"), 20.0)

        # Test upper boundary clamping
        res_high = controller.set_simulated_loss(0.95)
        self.assertEqual(res_high.get("simulated_loss_rate"), 0.50)

        # Reset to 0
        controller.set_simulated_loss(0.0)
        self.assertEqual(controller.simulated_loss_rate, 0.0)

    def test_udp_server_loss_rate_setting(self):
        """Test setting loss rate directly on UDPServer instance."""
        self.server.set_simulated_loss_rate(0.30)
        self.assertEqual(self.server.simulated_loss_rate, 0.30)

        self.server.set_simulated_loss_rate(0.0)
        self.assertEqual(self.server.simulated_loss_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
