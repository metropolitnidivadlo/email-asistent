import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asistent import kokpit, kontakty  # noqa: E402

HLAVICKA = "nazev;typ;mesto;kraj;web;email;telefon;kontaktni_osoba;pozice;poznamka;zdroj_url;overeno\n"
CSV = ("﻿" + HLAVICKA +
       "Žluťoučké divadlo;divadlo;Brno;Jihomoravský kraj;https://www.zluta.cz;info@zluta.cz;+420 111;;;;;2026-11-19\n"
       "Dům <b>kultury</b>;kulturni_dum;Aš;Karlovarský kraj;javascript:alert(1);bad\"@x.cz;;;;;;2026-11-19\n"
       "Gmail klub;festival;Opava;Moravskoslezský kraj;;klub@gmail.com;;;;;;2026-11-19\n").encode("utf-8")


class Priloha(unittest.TestCase):
    def test_round_trip(self):
        msg = kontakty.build_message("me@x.cz", CSV)
        self.assertEqual(msg["Subject"][:9], "Kontakty ")
        rows = kontakty.csv_z_prilohy(msg.as_bytes())
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["nazev"], "Žluťoučké divadlo")
        self.assertEqual(rows[0]["email"], "info@zluta.cz")
        att = [p for p in msg.walk() if p.get_filename()][0]
        self.assertEqual(att.get_content_type(), "text/csv")
        self.assertEqual(att.get_content_charset(), "utf-8")
        self.assertIn("3 záznamů", msg.get_body().get_content())

    def test_bez_prilohy(self):
        from email.message import EmailMessage
        m = EmailMessage()
        m.set_content("nic")
        self.assertEqual(kontakty.csv_z_prilohy(m.as_bytes()), [])


class VKontaktu(unittest.TestCase):
    def test_logika(self):
        k = kontakty.parse_csv(CSV)
        msgs = [{"addr": "pepa@zluta.cz", "to": "Me <me@x.cz>"},
                {"addr": "x@seznam.cz", "to": "klub@gmail.com"}]
        dom = kontakty.domeny_zprav(msgs, own="me@x.cz")
        self.assertEqual(dom, {"zluta.cz"})
        kontakty.oznac_v_kontaktu(k, dom)
        self.assertEqual([x["v_kontaktu"] for x in k], [True, False, False])

    def test_web_a_prijemce(self):
        k = [{"nazev": "A", "web": "https://www.dk-as.cz/kontakt", "email": ""}]
        dom = kontakty.domeny_zprav([{"addr": "me@x.cz", "to": "Ředitel <reditel@mail.dk-as.cz>"}])
        kontakty.oznac_v_kontaktu(k, dom)
        self.assertTrue(k[0]["v_kontaktu"])


class Render(unittest.TestCase):
    def _data(self, kont):
        return {"generated": "2026-11-19T10:00:00+01:00", "folders": {}, "drafts": {"count": 0, "items": []},
                "top_senders": {}, "reply": {}, "important_today": [], "kontakty": kont}

    def test_pet_sekci_a_prazdne(self):
        out = kokpit.render(self._data([]))
        for h in ("Dnes", "Pošta", "Představení a doprava", "Statistiky a finance", "Nové příležitosti"):
            self.assertIn(f">{h}</h2>", out)
        self.assertIn("Databáze kontaktů zatím není nahraná.", out)
        self.assertEqual(out.count("<section"), 5)

    def test_escape_a_odkazy(self):
        k = kontakty.parse_csv(CSV)
        kontakty.oznac_v_kontaktu(k, {"zluta.cz"})
        out = kokpit.render(self._data(k))
        self.assertNotIn("<b>kultury", out)
        self.assertIn("Dům &lt;b&gt;kultury&lt;/b&gt;", out)
        self.assertNotIn('href="javascript', out)
        self.assertIn('href="mailto:info@zluta.cz"', out)
        self.assertNotIn('href="mailto:bad', out)
        self.assertIn('href="https://www.zluta.cz" target="_blank" rel="noopener"', out)
        self.assertIn("<summary>Jihomoravský kraj (1)</summary>", out)
        self.assertIn("v kontaktu</span>", out)
        self.assertIn("nový", out)
        self.assertIn("Celkem: <strong>3</strong>", out)
        self.assertIn("festival 1", out)
        self.assertNotIn("<script", out)


if __name__ == "__main__":
    unittest.main()
