import re

def japanese_cleaners(text):
    from AronaTTS.text.japanese import japanese_to_romaji_with_accent
    text = japanese_to_romaji_with_accent(text)
    if len(text) == 0 or re.match('[A-Za-z]', text[-1]):
        text += '.'
    return text


def japanese_cleaners2(text):
    text = text.replace('・・・', '…').replace('・', ' ')
    text = japanese_cleaners(text).replace('ts', 'ʦ').replace('...', '…') \
                                    .replace('(', '').replace(')', '') \
                                    .replace('[', '').replace(']', '') \
                                    .replace('*', ' ').replace('{', '').replace('}', '')
    return text