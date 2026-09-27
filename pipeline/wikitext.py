"""Convert Wikipedia wikitext into plain text, keeping section headings as '== Title =='.

Removed: tables, references, infoboxes and other templates, files/images,
categories, comments. Kept: prose, with links replaced by their visible text.
A few inline templates that carry prose (unit conversions, name sorting,
no-wrap...) are replaced by their text instead of being removed.
"""
import re

import mwparserfromhell
from mwparserfromhell.nodes import Comment, Tag, Template, Wikilink

HEADING = re.compile(r'^(={2,6})\s*(.+?)\s*\1\s*$', re.M)

REMOVED_TAGS = {'ref', 'table', 'gallery', 'references', 'math', 'score', 'timeline', 'imagemap', 'sup'}
REMOVED_LINK_PREFIXES = ('file:', 'image:', 'category:', 'media:')

# template name -> function(template) returning the text it stands for
INLINE_TEMPLATES = {
    'convert': lambda t: f'{arg(t, 1)} {arg(t, 2)}',
    'cvt': lambda t: f'{arg(t, 1)} {arg(t, 2)}',
    'sortname': lambda t: f'{arg(t, 1)} {arg(t, 2)}',
    'nowrap': lambda t: arg(t, 1),
    'nobr': lambda t: arg(t, 1),
    'lang': lambda t: arg(t, 2),
    'transl': lambda t: arg(t, 2),
    'ill': lambda t: arg(t, 1),
    'interlanguage link': lambda t: arg(t, 1),
    'f1': lambda t: arg(t, 1),                             # {{F1|2022}} -> '2022'
    'f1 gp': lambda t: f'{arg(t, 2)} Grand Prix',           # {{F1 GP|2021|Abu Dhabi}} -> 'Abu Dhabi Grand Prix'
    'f1gp': lambda t: f'{arg(t, 2)} Grand Prix',
    'nbsp': lambda t: ' ',
    'spaces': lambda t: ' ',
    'space': lambda t: ' ',
    'thinsp': lambda t: ' ',
    'ndash': lambda t: '–',
    'mdash': lambda t: '—',
    'snd': lambda t: ' – ',
    'abbr': lambda t: arg(t, 1),
    'small': lambda t: arg(t, 1),
    'dts': lambda t: ' '.join(str(p.value).strip() for p in t.params if not p.showkey),
    'date': lambda t: arg(t, 1),
    'as of': lambda t: f'As of {arg(t, 1)}',
    'gp': lambda t: f'{arg(t, 1)} Grand Prix',
    'flagicon': lambda t: '',
}


def arg(template: Template, index: int) -> str:
    positional = [p for p in template.params if not p.showkey]
    if len(positional) < index:
        return ''
    return to_text(str(positional[index - 1].value))


def to_text(wikitext: str) -> str:
    code = mwparserfromhell.parse(wikitext)

    for node in code.filter(recursive=False):
        if isinstance(node, Comment):
            code.remove(node)
        elif isinstance(node, Tag) and str(node.tag).lower() in REMOVED_TAGS:
            code.remove(node)
        elif isinstance(node, Wikilink) and str(node.title).strip().lower().startswith(REMOVED_LINK_PREFIXES):
            code.remove(node)
        elif isinstance(node, Template):
            name = str(node.name).strip().lower().replace('_', ' ')
            replace = INLINE_TEMPLATES.get(name)
            code.replace(node, replace(node) if replace else '')

    text = code.strip_code(normalize=True, collapse=True, keep_template_params=False)

    text = re.sub(r'\(\s*[,;]?\s*\)', '', text)       # parentheses emptied by removed templates
    text = re.sub(r'\(\s*[,;]\s*', '(', text)         # '(; born ...' left by pronunciation templates
    text = re.sub(r'[ \t ​]+', ' ', text)
    text = re.sub(r' +([,.;:)])', r'\1', text)
    text = re.sub(r'\( +', '(', text)
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def wikitext_to_text(wikitext: str) -> str:
    """Convert an article section by section, so headings survive the conversion."""
    parts = HEADING.split(wikitext)
    output = [to_text(parts[0])]
    for level, title, body in zip(parts[1::3], parts[2::3], parts[3::3]):
        output.append(f'{level} {to_text(title)} {level}')
        output.append(to_text(body))
    return '\n\n'.join(part for part in output if part)
