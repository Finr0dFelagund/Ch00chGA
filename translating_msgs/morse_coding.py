from typing import Literal
import re
import string

ru_to_morse = {
    'а': ' .- ',
    'б': ' -... ',
    'в': ' .-- ',
    'г': ' --. ',
    'д': ' -.. ',
    'е': ' . ',
    'ж': ' ...- ',
    'з': ' --.. ',
    'и': ' .. ',
    'й': ' .--- ',
    'к': ' -.- ',
    'л': ' .-.. ',
    'м': ' -- ',
    'н': ' -. ',
    'о': ' --- ',
    'п': ' .--. ',
    'р': ' .-. ',
    'с': ' ... ',
    'т': ' - ',
    'у': ' ..- ',
    'ф': ' ..-. ',
    'х': ' .... ',
    'ц': ' -.-. ',
    'ч': ' ---. ',
    'ш': ' ---- ',
    'щ': ' --.- ',
    'ъ': ' .--.-. ',
    'ы': ' -.-- ',
    'ь': ' -..- ',
    'э': ' ...-... ',
    'ю': ' ..-- ',
    'я': ' .-.- '
}

en_to_morse = {
    'a': ' .- ',
    'b': ' -... ',
    'c': ' -.-. ',
    'd': ' -.. ',
    'e': ' . ',
    'f': ' ..-. ',
    'g': ' --. ',
    'h': ' .... ',
    'i': ' .. ',
    'j': ' .--- ',
    'k': ' -.- ',
    'l': ' .-.. ',
    'n': ' -- ',
    'm': ' -. ',
    'o': ' --- ',
    'p': ' .--. ',
    'q': ' --.- ',
    'r': ' .-. ',
    's': ' ... ',
    't': ' - ',
    'u': ' ..- ',
    'v': ' ...- ',
    'w': ' .-- ',
    'x': ' -..- ',
    'y': ' -.-- ',
    'z': ' --.. '
}

def morse_coding(in_str: str, lang: Literal['en', 'ru'], direction: Literal['lang', 'morse']) -> str:
    if direction == 'morse':
        in_str = re.sub(re.compile('|'.join(map(re.escape, string.punctuation + string.digits))), r'', in_str)
        in_str = re.sub(r'\s+', r'/', in_str)
        in_str = ' '.join(in_str).lower()
        if lang == 'en':
            pattern = re.compile('|'.join(map(re.escape, en_to_morse.keys())))
            def replacement_func(match):
                return en_to_morse[match.group()]
        elif lang == 'ru':
            pattern = re.compile('|'.join(map(re.escape, ru_to_morse.keys())))
            def replacement_func(match):
                return ru_to_morse[match.group()]
        in_str = pattern.sub(replacement_func, in_str)
        in_str = re.sub(r'  +', ' ', in_str)
        return in_str

    elif direction == 'lang':
        in_str = in_str.translate(str.maketrans('*_', '.-'))
        if lang == 'en':
            replacement_dict = {value: key for key, value in en_to_morse.items()}
            pattern = re.compile('|'.join(map(re.escape, en_to_morse.values())))
        elif lang == 'ru':
            replacement_dict = {value: key for key, value in ru_to_morse.items()}
            pattern = re.compile('|'.join(map(re.escape, ru_to_morse.values())))
        def replacement_func(match):
            return replacement_dict[match.group()]
        in_str = re.sub(r'\s{1}', '  ', in_str)
        in_str = ' ' + in_str + ' '
        in_str = pattern.sub(replacement_func, in_str)
        in_str = re.sub(r'\s\s\s\s+', r'/', in_str)
        in_str = re.sub(r'\s', r'', in_str)
        in_str = re.sub(r'/', r' ', in_str)
        return in_str