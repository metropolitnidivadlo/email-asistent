import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asistent import utf7, classify, config  # noqa: E402
from asistent.imap_client import Email, strip_quotes, html_to_text  # noqa: E402


def mk(**kw):
    base = dict(uid="1", message_id="<a@b>", from_name="X", from_addr="x@example.cz", to="info@x.cz",
                date="", subject="Test", text="Ahoj")
    base.update(kw)
    return Email(**base)


class T(unittest.TestCase):
    def test_utf7(self):
        for s in ["Představení a zájezdy", "Nabídky a objednávky", "Faktury & finance", "INBOX", "Ostatní"]:
            self.assertEqual(utf7.decode(utf7.encode(s)), s)
        self.assertEqual(utf7.encode("A&B"), "A&-B")
        self.assertEqual(utf7.encode("Doprava"), "Doprava")
        self.assertEqual(utf7.encode("☺"), "&Jjo-")  # příklad z RFC 3501 / 2152

    def test_pravidla(self):
        self.assertEqual(classify.rule_based(mk(list_unsubscribe="<mailto:x>")).folder, "Newslettery")
        self.assertEqual(classify.rule_based(mk(precedence="bulk")).folder, "Newslettery")
        self.assertEqual(classify.rule_based(mk(auto_submitted="auto-generated")).folder, "Newslettery")
        self.assertEqual(classify.rule_based(mk(from_addr="no-reply@firma.cz")).folder, "Newslettery")
        self.assertFalse(classify.rule_based(mk(from_addr="no-reply@firma.cz")).needs_reply)
        self.assertIsNone(classify.rule_based(mk(auto_submitted="no")))
        self.assertIsNone(classify.rule_based(mk()))

    def test_fallback(self):
        self.assertEqual(classify.keyword_fallback(mk(subject="Faktura č. 5")).folder, "Faktury a finance")
        self.assertEqual(classify.keyword_fallback(mk()).folder, config.FOLDER_OTHER)

    def test_citace(self):
        t = "Děkuji.\n> staré\nDne 1. 1. 2026 Jan napsal:\nstarší"
        self.assertEqual(strip_quotes(t), "Děkuji.")

    def test_html(self):
        self.assertIn("Ahoj světe", html_to_text("<p>Ahoj <b>světe</b></p><script>x</script>"))


if __name__ == "__main__":
    unittest.main()
