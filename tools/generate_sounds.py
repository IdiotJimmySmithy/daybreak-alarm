"""Generate original, deterministic, low-amplitude PCM alarm sounds."""

from array import array
import math
from pathlib import Path
import sys
import wave

DEST = Path(__file__).resolve().parents[1] / "custom_components/daybreak_alarm/frontend/sounds"
SAMPLE_RATE = 22050


def build():
    DEST.mkdir(parents=True, exist_ok=True)
    for name, notes in {"daybreak": [523.25, 659.25, 783.99, 1046.5], "soft": [392, 493.88, 587.33, 783.99], "pulse": [880, 880, 1174.66, 880]}.items():
        samples = array("h")
        for i in range(SAMPLE_RATE * 6):
            t = i / SAMPLE_RATE
            beat = int(t / 1.25)
            local = t % 1.25
            if beat >= len(notes) or local > 0.95:
                value = 0
            else:
                envelope = min(local / 0.025, 1) * math.exp(-local * (5 if name == "pulse" else 3))
                frequency = notes[beat]
                value = 0.22 * envelope * (math.sin(2 * math.pi * frequency * local) + 0.2 * math.sin(4 * math.pi * frequency * local))
            samples.append(int(value * 32767))
        if sys.byteorder != "little":
            samples.byteswap()
        with wave.open(str(DEST / f"{name}.wav"), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(SAMPLE_RATE)
            output.writeframes(samples.tobytes())
        print(f"Generated {name}.wav: 6 seconds, PCM mono")


if __name__ == "__main__":
    build()
