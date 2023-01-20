import requests
from tqdm import tqdm
import time
from bs4 import BeautifulSoup
import re
import json
from typing import List

MAIN_URL = "http://emargo.pl"

def process_data(item_data: str) -> dict:
    # proces data for loading
    replace_keys = ['item', 'monster', 'npc', 'quest']
    item_data = item_data.replace(";var R =", '').replace("\n", '')
    for key in replace_keys:
        item_data = re.sub(f"\s{key}:\s", f'"{key}":', item_data)
    loaded = json.loads(item_data[:-1])
    # flaten structure
    for element in list(loaded.keys()):
        temp_inner_data = []
        for inner_key in loaded[element]:
            temp_inner_data.append(loaded[element][inner_key])
        loaded[element] = temp_inner_data
    return loaded


def process_classes(classes_string: str) -> List[str]:
    classes_dict = {"p": "Paladyn", "w": "Wojownik", "b": "Tancerz Ostrzy", "m": "Mag", "t": "Tropiciel", "h": "Łowca"}
    return [classes_dict[initial] for initial in classes_string]

def stat_transform(item_loaded_data: dict) -> dict:
    TYPES = ['heroic', 'unique', 'legendary']
    BINDING = ['binds', 'soulbound']
    # change stats
    for item in item_loaded_data['item']:
        stats_split=item['stats'].split("||")
        # add value to item dict
        item['value'] = stats_split[-1]
        # create stat dict, hp: 1, dmg, 10-15 etc and add to main item dict
        stats_dict = {}
        for stat in stats_split[1].split(";"):
            element_split = stat.split("=")
            if len(element_split) == 2:
                stats_dict[element_split[0]] = element_split[1]

                # process classes
                if element_split[0] == "reqp":
                    stats_dict['reqp'] = process_classes(element_split[1])
                
            # handle rarity and binding
            else:
                if element_split[0] in TYPES:
                    stats_dict['rarity'] = element_split[0]
                if element_split[0] in BINDING:
                    stats_dict['binding'] = element_split[0]
        item['stats'] = stats_dict

    # flaten items
    if len(item_loaded_data['item']) == 1:
        item_loaded_data['item'] = item_loaded_data['item'][0]

    return item_loaded_data

def get_item_data(item_path) -> dict:
    item_soup = BeautifulSoup(requests.get(item_path).text)
    item_data = item_soup.find("script", string=re.compile(";var R.*")).text
    return stat_transform(process_data(item_data))

def main():
    items = []
    item_page = BeautifulSoup(requests.get(f"{MAIN_URL}/przedmioty/").text)
    pbar = tqdm(item_page.find_all("a", {"href": re.compile("\/przedmioty\/dla.*")}))
    for element_index, element_a in enumerate(pbar):
        soup_items = BeautifulSoup(requests.get(MAIN_URL + element_a['href']).text)
        items_tags = soup_items.find_all("a", {"href": re.compile("\/przedmiot\/.*")})
        for item_index, item in enumerate(items_tags[:1]):
            pbar.set_description(f"Profession: {element_a['href'].split('/')[-2]}, Item Type: {element_a.text}, Item count: {item_index+1}/{len(items_tags)}")
            time.sleep(0.5)
            data_dict = get_item_data(MAIN_URL + item['href'])
            data_dict['item']['type'] = element_a.text
            items.append(data_dict)
    with open("emargo.json", "w", encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False)
    return items

if __name__ == "__main__":
    main()