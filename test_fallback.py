from difflib import get_close_matches

def validate(monumento, titulo):
    if titulo and not get_close_matches(monumento.lower(), [titulo.lower()], cutoff=0.3):
        return None
    return titulo

print(validate("castillo lizar", "List of songs recorded by Shakira"))
print(validate("castillo lizar", "Castillo de Frigiliana"))
