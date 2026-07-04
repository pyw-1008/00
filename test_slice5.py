import unittest

import server


class Slice5QrTest(unittest.TestCase):
    def test_audience_url_uses_request_host(self):
        self.assertEqual(
            server.make_audience_url("192.168.1.8:8000"),
            "http://192.168.1.8:8000/audience",
        )

    def test_qr_svg_is_generated_locally(self):
        svg = server.make_qr_svg("http://127.0.0.1:8000/audience")

        self.assertIn("<svg", svg)
        self.assertIn("<rect", svg)
        self.assertIn("http://127.0.0.1:8000/audience", svg)

    def test_qr_matrix_decodes_to_audience_url(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("cv2 or numpy is not available")

        url = "http://127.0.0.1:8000/audience"
        modules = server.make_qr_modules(url)
        quiet_zone = 4
        scale = 10
        size = (len(modules) + quiet_zone * 2) * scale
        image = np.full((size, size), 255, dtype=np.uint8)

        for y, row in enumerate(modules):
            for x, dark in enumerate(row):
                if dark:
                    y1 = (y + quiet_zone) * scale
                    x1 = (x + quiet_zone) * scale
                    image[y1:y1 + scale, x1:x1 + scale] = 0

        decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
        self.assertEqual(decoded, url)


if __name__ == "__main__":
    unittest.main()
