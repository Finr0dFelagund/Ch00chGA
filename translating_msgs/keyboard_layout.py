from typing import Literal

en_str = r'''`qwertyuiop[]asdfghjkl;'zxcvbnm,./~@#$%^&QWERTYUIOP{}|ASDFGHJKL:"ZXCVBNM<>?'''
ru_str = r'''ёйцукенгшщзхъфывапролджэячсмитьбю.Ё"№;%:?ЙЦУКЕНГШЩЗХЪ/ФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,'''

def change_kb_layout(in_str: str, route: Literal['to_en', 'to_ru']) -> str:
    """Меняет раскладку текста: русская ↔ английская."""
    if route == 'to_en':
        return in_str.translate(str.maketrans(ru_str, en_str))
    else:
        return in_str.translate(str.maketrans(en_str, ru_str))
