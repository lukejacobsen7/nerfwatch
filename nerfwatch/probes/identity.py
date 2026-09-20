"""Identity-layer probes: fixed, boring completion prompts, 1 output token each.

They never rotate. Their only job is to be a stable ruler: if the served
weights, quantization, sampling stack or system prompt change, the top-token
logprobs across this set move together (arXiv 2512.03816). Which subset of the
pool you use is chosen by your salt, so no two installs share an exact set.
"""

from __future__ import annotations

import hashlib
import random

POOL = [
    "The capital of France is", "Water boils at a temperature of", "The opposite of hot is", "Two plus two equals",
    "The largest planet in our solar system is", "A triangle has this many sides:", "The color of the sky on a clear day is",
    "The chemical symbol for gold is", "Shakespeare wrote a play called", "The first month of the year is",
    "Photosynthesis happens in the", "The square root of 81 is", "A baby cat is called a", "The Pacific is an",
    "Bread is made from", "The human heart pumps", "In Python, a list is created with", "The speed of light is approximately",
    "Mount Everest is located in", "The currency of Japan is the", "A week has this many days:", "Ice is frozen",
    "The author of 1984 is", "Spiders have this many legs:", "The freezing point of water in Celsius is",
    "The primary language spoken in Brazil is", "The moon orbits the", "A hexagon has", "The boiling point of water in Fahrenheit is",
    "HTML stands for", "The smallest prime number is", "Penguins live mostly in", "A decade is", "The Great Wall is in",
    "To sort a list in Python you call", "The Roman numeral for ten is", "Sound travels faster in", "A synonym for big is",
    "The longest river in Africa is", "The number of continents is", "Copper conducts", "The past tense of run is",
    "An octopus has", "A leap year has", "The main gas in Earth's atmosphere is", "Fish breathe using", "The plural of mouse is",
    "Bees make", "The inventor of the telephone is usually said to be", "A century is", "The tallest animal is the",
    "The hardest natural substance is", "Lightning is followed by", "The capital of Japan is", "Seven times eight is",
    "The chemical formula for water is", "A group of lions is called a", "The largest ocean is the", "Milk comes from",
    "The Earth rotates once every", "The primary colors are red, blue and", "Cats are known for chasing", "A year has this many months:",
]


def select(salt: str, n: int) -> list[str]:
    seed = int(hashlib.sha256(f"{salt}|identity".encode()).hexdigest(), 16) % (2**63)
    rng = random.Random(seed)
    return rng.sample(POOL, min(n, len(POOL)))


def probe_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]
