import re
import unidecode

always_lowercase_words = {
    "and", "or", "of", "but", "for", "nor", "the", "a", "an", "as", "down",
    "under", "over", "to", "through", "during", "without", "on", "in", "by", "off",
    "from"
}

# Updated regex to include dashes within words
ONLY_WORDS_REGEX = r"[^\W\d_][\w\-']*"  # allows dash and apostrophes in words

def is_all_capitalized(word: str) -> bool:
    return word.upper() == word

def is_irregular_capitalized(word: str) -> bool:
    if is_all_capitalized(word):
        return False
    rest = unidecode.unidecode(word[1:])
    return bool(re.search(r"[A-Z]", rest))

def to_title_case(text: str) -> str:
    words = list(re.finditer(ONLY_WORDS_REGEX, text))
    if not words:
        return text

    total = len(words)

    def replace(match: re.Match, index=[0]):
        word = match.group(0)
        i = index[0]
        index[0] += 1

        lowercase = word.lower()

        # Don't change all-uppercase, irregular, or numeric words
        if word.isdigit() or is_all_capitalized(word) or is_irregular_capitalized(word):
            return word

        if i == 0 or i == total - 1:
            return word.capitalize()
        elif lowercase in always_lowercase_words:
            return lowercase
        else:
            return word.capitalize()

    return re.sub(ONLY_WORDS_REGEX, replace, text)