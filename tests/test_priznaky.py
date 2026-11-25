import unittest

from asistent import priznaky


class TestPriznaky(unittest.TestCase):
    def test_parse_fetch(self):
        data = [(b'1 (UID 42 FLAGS (\Seen $AsistentHotovo) BODY[HEADER.FIELDS (MESSAGE-ID)] {30}',
                 b'Message-ID: <abc@x.cz>\r\n\r\n'), b')',
                (b'2 (UID 43 FLAGS ($AsistentHotovo \Answered \Seen) BODY[HEADER.FIELDS (MESSAGE-ID)] {30}',
                 b'Message-Id: <def@y.cz>\r\n\r\n'), b')']
        out = priznaky.parse_fetch(data)
        self.assertEqual(out["<abc@x.cz>"], ("42", {"\Seen"}))
        self.assertEqual(out["<def@y.cz>"], ("43", {"\Seen", "\Answered"}))

    def test_rozdil(self):
        self.assertEqual(priznaky.rozdil({"\Seen", "\Answered"}, set()), ({"\Seen", "\Answered"}, set()))
        self.assertEqual(priznaky.rozdil(set(), {"\Seen"}), (set(), {"\Seen"}))
        self.assertEqual(priznaky.rozdil({"\Seen"}, {"\Seen"}), (set(), set()))


if __name__ == "__main__":
    unittest.main()
