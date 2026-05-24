from difflib import get_close_matches
print("1", get_close_matches("castillo lizar", ["list of songs recorded by shakira"], cutoff=0.2))
print("2", get_close_matches("castillo lizar", ["castillo de frigiliana"], cutoff=0.2))
print("3", get_close_matches("alhambra", ["alhambra (granada)"], cutoff=0.2))
