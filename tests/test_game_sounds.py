import subprocess, sys, tempfile, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import highlights


class GameSounds(unittest.TestCase):
    def test_gunfire_and_boom_stand_out(self):
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / 'b.wav'
            shots = ''.join(f'[g{i}]adelay={20000 + 150 * i}[a{i}];' for i in range(6))
            graph = '[2]asplit=6' + ''.join(f'[g{i}]' for i in range(6)) + ';' + shots + '[1]volume=25,adelay=45000[b];[0]' + ''.join(f'[a{i}]' for i in range(6)) + '[b]amix=inputs=8:normalize=0'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anoisesrc=d=60:c=pink:a=0.02', '-f', 'lavfi', '-i', 'sine=f=60:d=0.4',
                            '-f', 'lavfi', '-i', 'anoisesrc=d=0.05:c=white:a=0.9', '-filter_complex', graph, '-ar', '16000', str(wav)], check=True)
            rms, hf, bursts, booms = highlights._audio(wav)
        n = len(rms)
        bang = np.maximum(highlights._z(bursts, n, 300), highlights._z(booms, n, 300))
        self.assertEqual(set(int(i) for i in np.argsort(-bang)[:2]), {20, 45})


if __name__ == '__main__':
    unittest.main()
