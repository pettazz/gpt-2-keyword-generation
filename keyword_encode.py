import spacy
import csv
import re
import multiprocessing
from functools import partial
from tqdm import tqdm
from itertools import chain
from random import random, shuffle

DELIMS = {
    'section': '~',
    'category': '`',
    'keywords': '^',
    'title': '@',
    'body': '}'
}

PRONOUNS = set(['i', 'me', 'we', 'you', 'he', 'she',
                'it', 'him', 'her', 'them', 'they'])


def build_section(section, text):
    if text is None:
        return ''
    return DELIMS['section'] + DELIMS[section] + text


def encode_keywords(csv_path, model='en_core_web_sm',
                    category_field=None,
                    keywords_field=None,
                    title_field=None,
                    body_field=None,
                    keyword_gen='title',
                    keyword_sep=',',
                    dropout=0.5,
                    repeat=3,
                    max_keywords=3,
                    keyword_length_max=20,
                    out_path='csv_encoded.txt',
                    start_token="<|startoftext|>",
                    end_token="<|endoftext|>"):

    data_list = []
    nlp = spacy.load(model)
    pattern = re.compile('\W+')

    func = partial(generate_encoded_text, nlp, pattern,
                   model,
                   category_field,
                   keywords_field,
                   title_field,
                   body_field,
                   keyword_gen,
                   keyword_sep,
                   dropout,
                   repeat,
                   max_keywords,
                   keyword_length_max,
                   out_path,
                   start_token,
                   end_token)

    with open(csv_path, 'r', encoding='utf8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data_list.append(row)

    shuffle(data_list)
    
    with multiprocessing.Pool(multiprocessing.cpu_count()) as p:
        with open(out_path, 'w', encoding='utf8', errors='ignore') as w:
            pbar = tqdm(total=len(data_list), smoothing=0)
            for result in p.imap_unordered(func, data_list):
                pbar.update(1)
                for encoded_text in result:
                    w.write(encoded_text)
            pbar.close()


def generate_encoded_text(nlp, pattern,
                          model,
                          category_field,
                          keywords_field,
                          title_field,
                          body_field,
                          keyword_gen,
                          keyword_sep,
                          dropout,
                          repeat,
                          max_keywords,
                          keyword_length_max,
                          out_path,
                          start_token,
                          end_token,
                          row):

    # category should be normalized to account for user input
    category = re.sub(
        pattern, '-', row[category_field].lower().strip()) if category_field is not None else None

    title = row[title_field] if title_field is not None else None
    body = row[body_field] if body_field is not None else None

    if keywords_field is None:
        # Generate the keywords using spacy
        doc = nlp(row[keyword_gen])
        keywords = [[chunk.text, chunk.root.text]
                    for chunk in doc.noun_chunks]
        keywords = [re.sub(pattern, '-', text.lower())
                    for text in chain.from_iterable(keywords)
                    if len(text) <= keyword_length_max]
    else:
        keywords = [re.sub(pattern, '-', keyword.lower().strip())
                    for keyword in row[keyword_gen].split(keyword_sep)]

    keywords = set(keywords) - PRONOUNS   # dedupe + remove pronouns

    encoded_texts = []
    for _ in range(repeat):
        new_keywords = [keyword for keyword in keywords
                        if random() < dropout]
        shuffle(new_keywords)
        new_keywords = " ".join(new_keywords[:max_keywords])

        encoded_texts.append(start_token +
                             build_section('category', category) +
                             build_section('keywords', new_keywords) +
                             build_section('title', title) +
                             build_section('body', body) +
                             end_token + "\n")
    return encoded_texts
