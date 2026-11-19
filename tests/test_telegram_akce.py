import os
import sys
import unittest
from email.message import EmailMessage
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asistent import telegram, telegram_akce as ta  # noqa: E402


def _koncept(body="Dobrý den,\n\nděkujeme.\n"):
    m = EmailMessage()
    m["From"] = "info@x.cz"
    m["To"] = "Jan Novák <jan@firma.cz>"
    m["Subject"] = "Re: Poptávka"
    m["In-Reply-To"] = "<orig@firma.cz>"
    m["References"] = "<a@b> <orig@firma.cz>"
    m["X-Asistent-Id"] = "ab12cd34"
    m["X-Mozilla-Draft-Info"] = "x"
    m.set_content(body)
    return m.as_bytes()


class Parsovani(unittest.TestCase):
    def test_callback(self):
        self.assertEqual(ta.parse_callback("send:ab12cd34"), ("send", "ab12cd34"))
        self.assertEqual(ta.parse_callback("sendok:ab12cd34"), ("sendok", "ab12cd34"))
        for bad in ("", None, "send:", "send:XYZ", "rm:ab12cd34", "send:ab12cd34;x", "send:ab12cd345"):
            self.assertIsNone(ta.parse_callback(bad))

    def test_filtr_chatu(self):
        def upd(chat):
            return {"update_id": 1, "callback_query": {"id": "c", "data": "send:ab12cd34",
                    "message": {"message_id": 5, "text": "t", "chat": {"id": chat}}}}
        self.assertEqual(len(ta.extract_actions([upd(111)], "111")), 1)
        self.assertEqual(ta.extract_actions([upd(222)], "111"), [])
        self.assertEqual(ta.extract_actions([{"update_id": 2, "message": {"chat": {"id": 111}, "text": "hi"}}], "111"), [])
        self.assertEqual(ta.extract_actions([upd(111)], None), [])


class Odchozi(unittest.TestCase):
    def test_hlavicky(self):
        out = ta.build_outgoing(_koncept(), "info@x.cz")
        self.assertEqual(out["From"], "info@x.cz")
        self.assertIn("jan@firma.cz", out["To"])
        self.assertEqual(out["In-Reply-To"], "<orig@firma.cz>")
        self.assertEqual(out["References"], "<a@b> <orig@firma.cz>")
        self.assertEqual(out["Subject"], "Re: Poptávka")
        self.assertIsNone(out["X-Asistent-Id"])
        self.assertTrue(out["Date"] and out["Message-ID"].endswith("@x.cz>"))
        self.assertNotIn("Draft", out.as_string())
        self.assertIn("děkujeme", out.get_body().get_content())


class Akce(unittest.TestCase):
    def _act(self, a):
        return {"action": a, "id": "ab12cd34", "callback_id": "c", "chat": 1, "message_id": 2, "text": "Koncept"}

    def test_chybejici_koncept_neodesle(self):
        for a in ("send", "sendok", "drop"):
            with mock.patch.object(ta, "find_draft", return_value=None), \
                    mock.patch.object(ta.smtp_send, "send") as snd, \
                    mock.patch.object(ta.telegram, "edit_message") as ed, \
                    mock.patch.object(ta.telegram, "answer_callback") as an:
                ta.handle(self._act(a), mock.Mock())
                snd.assert_not_called()
                self.assertIn("už ve složce není", ed.call_args[0][2])
                an.assert_called_once()

    def test_sendok_odesle_a_smaze(self):
        mb = mock.Mock(user="info@x.cz")
        with mock.patch.object(ta, "find_draft", return_value=("9", _koncept())), \
                mock.patch.object(ta.smtp_send, "send") as snd, \
                mock.patch.object(ta, "delete_draft") as dl, \
                mock.patch.object(ta, "mark_answered") as ma, \
                mock.patch.object(ta.telegram, "edit_message") as ed, \
                mock.patch.object(ta.telegram, "answer_callback"):
            ta.handle(self._act("sendok"), mb)
            snd.assert_called_once()
            dl.assert_called_once_with(mb, "9")
            ma.assert_called_once()
            self.assertIn("Odesláno", ed.call_args[0][2])

    def test_smtp_selhani_ponecha_koncept(self):
        with mock.patch.object(ta, "find_draft", return_value=("9", _koncept())), \
                mock.patch.object(ta.smtp_send, "send", side_effect=OSError("x")), \
                mock.patch.object(ta, "delete_draft") as dl, \
                mock.patch.object(ta.telegram, "edit_message") as ed, \
                mock.patch.object(ta.telegram, "answer_callback"):
            ta.handle(self._act("sendok"), mock.Mock(user="info@x.cz"))
            dl.assert_not_called()
            self.assertIn("Odeslání selhalo", ed.call_args[0][2])

    def test_doplnit_se_neodesle(self):
        with mock.patch.object(ta, "find_draft", return_value=("9", _koncept("Cena [DOPLNIT: cena]"))), \
                mock.patch.object(ta.smtp_send, "send") as snd, \
                mock.patch.object(ta.telegram, "edit_message"), \
                mock.patch.object(ta.telegram, "answer_callback"):
            ta.handle(self._act("sendok"), mock.Mock(user="info@x.cz"))
            snd.assert_not_called()

    def test_send_jen_potvrzeni(self):
        with mock.patch.object(ta, "find_draft", return_value=("9", _koncept())), \
                mock.patch.object(ta.smtp_send, "send") as snd, \
                mock.patch.object(ta.telegram, "edit_message") as ed, \
                mock.patch.object(ta.telegram, "answer_callback"):
            ta.handle(self._act("send"), mock.Mock())
            snd.assert_not_called()
            self.assertIn("Opravdu odeslat na", ed.call_args[0][2])
            self.assertEqual(ed.call_args[0][3][0][0]["callback_data"], "sendok:ab12cd34")

    def test_nanecisto_nic_nedela(self):
        with mock.patch.object(ta, "find_draft") as fd, mock.patch.object(ta.smtp_send, "send") as snd:
            ta.handle(self._act("sendok"), None, nanecisto=True)
            fd.assert_not_called()
            snd.assert_not_called()


class Karta(unittest.TestCase):
    def test_zkraceni(self):
        t = telegram.card_text("a@b.cz", "Předmět", "shrnutí", "x" * 9000)
        self.assertLessEqual(len(t), 4000)
        self.assertIn("zkráceno", t)
        self.assertEqual(telegram.keyboard_draft("ab12cd34")[0][0]["callback_data"], "send:ab12cd34")


if __name__ == "__main__":
    unittest.main()
