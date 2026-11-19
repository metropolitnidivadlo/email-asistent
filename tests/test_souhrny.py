import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asistent import config, kokpit, souhrny  # noqa: E402


def _ukol(**kw):
    u = {"text": "Zavolat dopravci", "termin": "2026-11-25", "priorita": "vysoká", "zdroj": "Doprava"}
    u.update(kw)
    return u


class Blok(unittest.TestCase):
    def test_round_trip_souhrnu(self):
        results = [{"uid": "5", "datum": "2026-11-19T09:00:00+01:00", "od": "a@b.cz", "predmet": "Žluťoučký kůň",
                    "folder": "Doprava", "important": True, "needs_reply": True,
                    "summary": "Pozor: \"uvozovky\" a ---", "koncept": True}]
        obj, body = souhrny.build_summary(results)
        self.assertEqual(souhrny.parse_block(body), obj)
        self.assertEqual(obj["pocet"], 1)
        self.assertEqual(obj["zpravy"][0]["predmet"], "Žluťoučký kůň")
        self.assertTrue(body.count(souhrny.JSON_START) == 1 and souhrny.JSON_END in body)

    def test_zprava_ma_prijem_utf8(self):
        _, body = souhrny.build_summary([])
        msg = souhrny.build_message("me@x.cz", "Souhrn 2026-11-19 10:00", body)
        raw = msg.as_bytes()
        self.assertEqual(souhrny.parse_block(souhrny._body(raw)), souhrny.parse_block(body))
        self.assertIn("text/plain", msg.get_content_type())
        self.assertEqual(msg.get_content_charset(), "utf-8")

    def test_chybny_json(self):
        self.assertIsNone(souhrny.parse_block("a\n---JSON---\n{rozbite\n---/JSON---"))
        self.assertIsNone(souhrny.parse_block("nic"))
        self.assertIsNone(souhrny.parse_block(None))

    def test_posledni_platny_blok(self):
        t = souhrny.build_block({"a": 1}) + "\n" + souhrny.build_block({"a": 2})
        self.assertEqual(souhrny.parse_block(t), {"a": 2})

    def test_round_trip_ukolu(self):
        obj, err = souhrny.validate_tasks({"vytvoreno": "x", "ukoly": [_ukol()], "poznamka": "p"})
        self.assertEqual(err, [])
        msg = souhrny.build_tasks_message(obj, "me@x.cz")
        self.assertTrue(msg["Subject"].startswith("Úkoly "))
        self.assertEqual(souhrny.parse_block(souhrny._body(msg.as_bytes())), obj)


class Validace(unittest.TestCase):
    def test_platne(self):
        obj, err = souhrny.validate_tasks({"ukoly": [_ukol(termin=None, zdroj=None)]})
        self.assertEqual(err, [])
        self.assertEqual(len(obj["ukoly"]), 1)

    def test_chyby(self):
        for bad in (_ukol(text=""), _ukol(text="x" * 301), _ukol(termin="25.11.2026"),
                    _ukol(termin="2026-13-40"), _ukol(priorita="kritická"), _ukol(priorita=None)):
            obj, err = souhrny.validate_tasks({"ukoly": [bad]})
            self.assertIsNone(obj)
            self.assertTrue(err, bad)

    def test_max_text_a_pocet(self):
        self.assertEqual(souhrny.validate_tasks({"ukoly": [_ukol(text="x" * 300)]})[1], [])
        self.assertEqual(souhrny.validate_tasks({"ukoly": [_ukol()] * 30})[1], [])
        self.assertTrue(souhrny.validate_tasks({"ukoly": [_ukol()] * 31})[1])

    def test_spatna_struktura(self):
        self.assertTrue(souhrny.validate_tasks([])[1])
        self.assertTrue(souhrny.validate_tasks({"ukoly": "x"})[1])

    def test_telegram_razeni(self):
        obj, _ = souhrny.validate_tasks({"ukoly": [
            _ukol(text="nizky", priorita="nízká", termin=None),
            _ukol(text="vysoky", priorita="vysoká", termin="2026-12-01")]})
        t = souhrny.telegram_text(obj)
        self.assertLess(t.index("vysoky"), t.index("nizky"))
        self.assertIn("do 2026-12-01", t)


class Config(unittest.TestCase):
    def test_slozky(self):
        self.assertEqual(config.FOLDER_SOUHRNY, "Asistent - Souhrny")
        self.assertEqual(config.FOLDER_UKOLY, "Asistent - Úkoly")
        self.assertEqual(len(kokpit.config.FOLDERS), 6)  # klasifikátor je nedostává


class RenderUkoly(unittest.TestCase):
    def _data(self, ukoly):
        return {"generated": "2026-11-19T10:00:00+01:00", "folders": {}, "drafts": {"count": 0, "items": []},
                "top_senders": {}, "reply": {}, "important_today": [],
                "ukoly": {"vytvoreno": "2026-11-19T08:00", "ukoly": ukoly, "poznamka": "<b>pozn</b>"}}

    def test_prazdne(self):
        out = kokpit.render(self._data([]))
        self.assertIn("Zatím žádné úkoly.", out)
        self.assertEqual(out.count("<h2 "), 5)

    def test_bez_klice(self):
        d = self._data([])
        del d["ukoly"]
        self.assertIn("Zatím žádné úkoly.", kokpit.render(d))

    def test_escape_a_po_terminu(self):
        out = kokpit.render(self._data([
            {"text": "<script>alert(1)</script>", "termin": "2026-11-01", "priorita": "vysoká",
             "zdroj": "\"><img src=x>"},
            {"text": "Budoucí", "termin": "2026-12-01", "priorita": "nízká", "zdroj": None}]))
        self.assertNotIn("<script>", out)
        self.assertNotIn("<img", out)
        self.assertNotIn("<b>pozn", out)
        self.assertEqual(out.count("po termínu"), 1)
        self.assertIn("Vysoká priorita", out)
        self.assertLess(out.index("Úkoly a připomínky"), out.index("Důležité dnes"))
        self.assertEqual(out.count("<h2 "), 5)


if __name__ == "__main__":
    unittest.main()
