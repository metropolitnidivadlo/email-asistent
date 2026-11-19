import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asistent import kokpit  # noqa: E402


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexcol):
    h = hexcol.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class Kontrast(unittest.TestCase):
    def test_znamy_pomer(self):
        self.assertAlmostEqual(contrast("#000000", "#ffffff"), 21.0, places=1)

    def test_paletu_wcag_aa(self):
        for mode, p in kokpit.PALETTES.items():
            for fg, bg, minimum in kokpit.PAIRS:
                c = contrast(p[fg], p[bg])
                self.assertGreaterEqual(c, minimum, f"{mode}: {fg} na {bg} = {c:.2f} < {minimum}")

    def test_css_pouziva_paletu(self):
        for p in kokpit.PALETTES.values():
            for v in p.values():
                self.assertIn(v, kokpit.CSS)


class Render(unittest.TestCase):
    def test_escapuje_data(self):
        d = {"generated": "2026-11-19T10:00:00+01:00", "folders": {"INBOX": {
            "today": 1, "week": 1, "month": 1,
            "latest": [{"date": "2026-11-19T09:00:00+01:00", "from": "<script>x</script>",
                        "addr": "a@b.cz", "subject": "\"><img src=x onerror=1>"}]}},
            "drafts": {"count": 0, "items": []}, "top_senders": {}, "reply": {}, "important_today": []}
        out = kokpit.render(d)
        self.assertNotIn("<script>", out)
        self.assertNotIn("<img", out)
        self.assertIn('lang="cs"', out)
        for h in ("Dnes", "Pošta", "Představení a doprava", "Statistiky a finance"):
            self.assertIn(f">{h}</h2>", out)


if __name__ == "__main__":
    unittest.main()
