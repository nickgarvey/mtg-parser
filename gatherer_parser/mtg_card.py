#!/usr/bin/env python3

import concurrent.futures
import re
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup

CARD_URL_BASE = 'http://gatherer.wizards.com/Pages/Card/'
CARD_LIST_URL = 'http://gatherer.wizards.com/Pages/Search/Default.aspx?output=spoiler&method=text&action=advanced&set=+%5b%22Dark+Ascension%22%5d'

executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)

class Card():

    def __init__(self, url):
        # get_from_gather will be called concurrently. The constructor
        # returns but any attempt to access a property will block until
        # the get_from_gatherer thread is finished
        def get_from_gatherer(url):
            with urllib.request.urlopen(url) as response:
                soup = BeautifulSoup(response)
                _card_div = _get_card_div(soup, url)
                self._img_url = _get_card_img_url(_card_div)
                self._name = _get_card_name(_card_div)
                self._mana_cost = _get_card_mana_cost(_card_div)
                self._rarities = _get_card_rarities(_card_div)
                self._sets = _get_card_sets(self._rarities)
                self._text = _get_card_text(_card_div)
                self._types = _get_card_types(_card_div)
                self._subtypes = _get_card_subtypes(_card_div)
                self._colors = _get_card_colors(_card_div, self._mana_cost)
                self._power = _get_card_power(_card_div)
                self._toughness = _get_card_toughness(_card_div)
                self._loyalty = _get_card_loyalty(_card_div)
                self._assoc_card = _get_assoc_card(soup, _card_div)

        self._future_fetch = executor.submit(get_from_gatherer, url)

    def __getattr__(self, name):
        concurrent.futures.wait([self._future_fetch])
        if name == 'img_url':
            return self._img_url
        elif name == 'name':
            return self._name
        elif name == 'rarities':
            return self._rarities
        elif name == 'sets':
            return self._sets
        elif name == 'mana_cost':
            return self._mana_cost
        elif name == 'text':
            return self._text
        elif name == 'types':
            return self._types
        elif name == 'subtypes':
            return self._subtypes
        elif name == 'colors':
            return self._colors
        elif name == 'power':
            return self._power
        elif name == 'toughness':
            return self._toughness
        elif name == 'loyalty':
            return self._loyalty
        elif name == 'assoc_card':
            return self._assoc_card
        else:
            raise AttributeError

def _get_card_div(soup, url):
    """
    This function is needed because of the existance of flip and transform
    cards. This will return the div for the card that matches the title of
    the page
    """
    card_containers = soup.find_all('td', {'class' : 'cardComponentContainer'})
    title = soup.title.string
    if '&part=' in url:
        # The part query parameter is always at the end
        url_enc_name = url[url.rindex('part=') + len('part='):] 
        card_name = urllib.parse.unquote_plus(url_enc_name)
    else:
        card_name = title[:title.rindex('(')].strip()
    for card_div in card_containers:
        card_div_name = _get_card_name(card_div)
        if card_name == card_div_name:
            return card_div
    raise Exception("Unable to find main card div for " + card_name)

def _get_card_rarities(card_div):
    rarities = {}
    sets_div = card_div.find_all('div', id=lambda x: x and 'otherSetsRow' in x)
    if sets_div:
        sets_imgs = sets_div[0].find_all('img')
        for img in sets_imgs:
            matches = re.match(r'(.*) \((.*)\)\s*', img.get('title'))
            rarity = matches.group(2)
            card_set = matches.group(1)
            if not rarity in rarities:
                rarities[rarity] = [card_set]
            else:
                rarities[rarity].append(card_set)
    else:
        card_set = card_div.find_all('div', id=lambda x: x and 'currentSetSymbol' in x)[0].find_all('a')[1].string
        rarity = list(card_div.find_all('div', id=lambda x: x and 'rarityRow' in x)[0].children)[3].span.string.strip()
        rarities = {rarity: [card_set]}
    return rarities

def _get_card_img_url(card_div):
    return urllib.parse.urljoin(CARD_URL_BASE, card_div.find_all('img', id=lambda x: x and 'cardImage' in x)[0]['src'])

def _get_card_sets(rarities):
    card_sets = set()
    for set_list in rarities.values():
        for card_set in set_list:
            card_sets.add(card_set)
    return list(sorted(card_sets))

def _get_card_name(card_div):
    return list(card_div.find_all('div', id=lambda x: x and 'nameRow' in x)[0].children)[3].string.strip()

def _get_card_text(card_div):
    text_search = card_div.find_all('div', id=lambda x: x and 'textRow' in x)
    card_text = ''
    if text_search:
        text_boxes = text_search[0].find_all('div', {'class' : 'cardtextbox'})
        for text_box in text_boxes:
            # imgs -> symbol custom tag
            text = re.sub(r'<img[^>]*alt="([^"]+)"[^>]*>', r'<symbol type="\1">', str(text_box))
            # remove divs
            text = re.sub(r'</?div[^>]*>', '', text)
            # i -> nrt (not rule text)
            text = re.sub(r'<(/?)i>', r'<\1nrt>', text)
            card_text += text + '\n'
        card_text = card_text.strip()
    return card_text

def _get_card_mana_cost(card_div):
    mana_re = re.compile('.*name=([[0-9WUBRGXP]+).*')
    mana_cost = []
    mana_row_search = card_div.find_all('div', id=lambda x: x and 'manaRow' in x)
    if mana_row_search:
        mana_row = mana_row_search[0]
        mana_value = mana_row.find_all('div', {'class' : 'value'})[0]
        for img in mana_value.find_all('img'):
            mana = mana_re.match(img['src']).group(1)
            mana_cost.append(mana)
    return mana_cost


def _get_card_types(card_div):
    type_div = _get_type_div(card_div)
    return type_div.string.split('—')[0].strip().split(' ')

def _get_card_subtypes(card_div):
    type_div = _get_type_div(card_div)
    sub_types = []
    if '—' in type_div.string:
        sub_types.extend(type_div.string.split('—')[1].strip().split(' '))
    return sub_types

def _get_type_div(card_div):
    return list(card_div.find_all('div', id=lambda x: x and 'typeRow' in x)[0].children)[3]

def _get_card_colors(card_div, mana_cost):
    color_row_search  = card_div.find_all('div', id=lambda x: x and 'colorIndicatorRow' in x)
    if color_row_search:
        colors = [list(color_row_search[0].children)[3].string.strip()]
    else:
        color_set = set()
        for mana_symbol in mana_cost:
            if mana_symbol == 'W':
                color_set.add('White')
            elif mana_symbol == 'U':
                color_set.add('Blue')
            elif mana_symbol == 'B':
                color_set.add('Black')
            elif mana_symbol == 'R':
                color_set.add('Red')
            elif mana_symbol == 'G':
                color_set.add('Green')
        colors = sorted(list(color_set))
    return colors

def _get_card_power(card_div):
    pt_div = _get_pt_div(card_div)
    if pt_div:
        pt_str = list(pt_div.children)[3].string
        if '/' in pt_str:
            return pt_str.split('/')[0].strip()
    return None

def _get_card_loyalty(card_div):
    pt_div = _get_pt_div(card_div)
    if pt_div:
        pt_str = list(pt_div.children)[3].string
        if not '/' in pt_str:
            return pt_str.strip()
    return None

def _get_assoc_card(soup, main_card_div):
    card_containers = soup.find_all('td', {'class' : 'cardComponentContainer'})
    for card_div in card_containers:
        if main_card_div != card_div and card_div.find_all('div'):
            return _get_card_name(card_div)
    return None

def _get_card_toughness(card_div):
    pt_div = _get_pt_div(card_div)
    if pt_div:
        pt_str = list(pt_div.children)[3].string
        if '/' in pt_str:
            return pt_str.split('/')[1].strip()
    return None

def _get_pt_div(card_div):
    pt_div_search = card_div.find_all('div', id=lambda x: x and 'ptRow' in x)
    if pt_div_search:
        return pt_div_search[0]
    else:
        return None

def get_card_url_list(url_to_fetch):
    """
    This function expects a 'Text Spoiler' URL as the only argument.
    This URL will be parsed and a list of all of the card URLs for this
    page will be returned as a list

    Note that Unglued and Unhinged cards will cause unexpected behavior
    and should not be run through this method
    """
    url_list = []
    with urllib.request.urlopen(url_to_fetch) as response:
        soup = BeautifulSoup(response)
        text_div = soup.find_all('div', {'class': 'textspoiler'})[0]
        for child in text_div.find_all('a'):
            url = urllib.parse.urljoin(url_to_fetch, child['href'])
            # This is used to pick up cards like Akki Lavarunner
            if '(' in child.string:
                url += '&part=' + urllib.parse.quote_plus(re.match('.*\((.*)\)\s*', child.string).group(1))
            url_list.append(url)
    return url_list

cards = []
for i, url in enumerate(get_card_url_list(CARD_LIST_URL)):
    cards.append(Card(url))

for card in cards:
    print(card.name)
    print('', card.mana_cost)
    print('', card.sets)
    print('', card.types)
    print('', card.subtypes)
    print('', card.text)
    print('', card.rarities)
    print('PT', card.power, '/', card.toughness)
    print('L ', card.loyalty)
    print('', card.assoc_card)
    print()
