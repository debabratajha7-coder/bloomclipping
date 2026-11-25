import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import chat_replay


def chat():
    rows = []
    for s in range(70, 1200):
        rows.append((s, f'u{s % 7}', 'ok ok'))                       # steady background chat
        rows.append((s, 'greeter', 'hi bhai'))                        # greetings never count
    for i in range(40):
        rows.append((606 + i * .1, f'p{i}', 'KEKW 😂 hahaha'))       # 40 different people laugh right after 600 s
    for i in range(30):
        rows.append((906 + i * .1, 'spammer', 'POG POG'))            # one person spamming is not a crowd
    return rows


class ChatReplay(unittest.TestCase):
    def test_burst_of_people_with_kind_and_lag(self):
        sig = chat_replay.signals(chat(), 1200)
        score, kind = chat_replay.describe(sig, 595, 615)
        self.assertGreater(score, .8)
        self.assertEqual(kind, 'funny')
        self.assertLess(chat_replay.describe(sig, 895, 915)[0], .3)

    def test_ff_is_not_a_fail(self):
        self.assertIsNone(chat_replay.KINDS['fail'].search('ff khelte hai'))

    def test_no_chat(self):
        self.assertIsNone(chat_replay.signals([], 600))
        self.assertEqual(chat_replay.describe(None, 0, 10), (None, None))


if __name__ == '__main__':
    unittest.main()
