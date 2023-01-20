import requests
from tqdm import tqdm
import time
from bs4 import BeautifulSoup
import re
import json
from typing import List

MAIN_URL = "http://emargo.pl"

def process_data(item_data: str) -> dict:
    """Proces item data, remove unused characters for loading into dict, flatten dict one dimension 

    Args:
        item_data (str): Unprocessed text from javascript containing data about item, npcs, quests, drops

    Returns:
        dict: Processed item dict
    """
    
    # proces data for loading
    replace_keys = ['item', 'monster', 'npc', 'quest']
    item_data = item_data.replace(";var R =", '').replace("\n", '')
    for key in replace_keys:
        item_data = re.sub(f"\s{key}:\s", f'"{key}":', item_data)

    # slice last character for proper loading, remove ';'
    loaded: dict = json.loads(item_data[:-1])

    # flaten structure
    for element in loaded.keys():
        temp_inner_data = []
        for inner_key in loaded[element]:
            temp_inner_data.append(loaded[element][inner_key])
        loaded[element] = temp_inner_data
    return loaded


def process_classes(classes_string: str) -> List[str]:
    """Change initial of classes string to list of classes

    Args:
        classes_string (str): String containing letters of classes

    Returns:
        List[str]: List of classes coresponding to initials
    """

    classes_dict = {"p": "Paladyn", "w": "Wojownik", "b": "Tancerz Ostrzy", "m": "Mag", "t": "Tropiciel", "h": "Łowca"}
    return [classes_dict[initial] for initial in classes_string]

def stat_transform(item_loaded_data: dict) -> dict:
    """Transform stat info into dictionary, map rarity and binding to useable form, flatten items if possible

    Args:
        item_loaded_data (dict): item dict with unchanged data

    Returns:
        dict: Item with procesed stats, value
    """


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

    # flaten items, list not needed
    if len(item_loaded_data['item']) == 1:
        item_loaded_data['item'] = item_loaded_data['item'][0]

    return item_loaded_data

def get_item_data(item_path: str) -> dict:
    """Retrieve data from item page and pass to inner function, sleep if request status is not correct and retry

    Args:
        item_path (str): href to item page

    Returns:
        dict: procesed dictionary with item data
    """

    item_page_request = requests.get(item_path)
    if item_page_request.status_code != 200:
        time.sleep(20)
        item_page_request = requests.get(item_path)
    item_soup = BeautifulSoup(item_page_request.text, features="lxml")
    item_data = item_soup.find("script", string=re.compile(";var R.*")).text
    return stat_transform(process_data(item_data))

def get_other_items(listing_soup: BeautifulSoup, main_list: List[dict], element_type: str) -> None:
    """Get other elements than eq items. iterate through listing and get data

    Args:
        listing_soup (BeautifulSoup): Soup with listing of items
        main_list (List[dict]): Main list containing result to append
        element_type (str): type of element added
    """
    for item in set(listing_soup.find_all("a", {"href": re.compile("\/przedmiot\/.*")})):
        time.sleep(1)
        data_dict = get_item_data(MAIN_URL+item['href'])
        data_dict['item']['type'] = element_type
        main_list.append(data_dict)
    return

def main() -> None:
    """Main function for retriving data from `http://emargo.pl`, iterates through item types and items of given type.
    Saves results to `emargo.json` file

    """
    items = []
    # start from page of item types
    item_types_page = BeautifulSoup(requests.get(f"{MAIN_URL}/przedmioty/").text, features="lxml")
    # iterate through links of items types
    pbar = tqdm(item_types_page.find_all("a", {"href": re.compile("\/przedmioty\/dla.*")}))
    for element_index, element_a in enumerate(pbar):
        items_list_request = requests.get(MAIN_URL + element_a['href'])
        if items_list_request.status_code != 200:
            time.sleep(20)
            items_list_request = requests.get(MAIN_URL + element_a['href'])
        soup_items = BeautifulSoup(items_list_request.text, features="lxml")
        items_tags = soup_items.find_all("a", {"href": re.compile("\/przedmiot\/.*")})
        
        # get data from items of given type
        for item_index, item in enumerate(items_tags):
            pbar.set_description(f"Profession: {element_a['href'].split('/')[-2]}, Item Type: {element_a.text}, Item count: {item_index+1}/{len(items_tags)}")
            time.sleep(1)
            data_dict = get_item_data(MAIN_URL + item['href'])
            data_dict['item']['type'] = element_a.text
            items.append(data_dict)

    # get other items than equipment
    pbar_other = tqdm(item_types_page.find_all("a", {"href": re.compile("\/przedmioty\/(?!dla).*")})[:1])
    for element in pbar_other:
        time.sleep(1)
        type_listing = BeautifulSoup(requests.get(MAIN_URL+element['href']).text, features="lxml")
        max_page_number = type_listing.find("span", {"class": "last"}).find("a")['href'].split("-")[-1]
        # get first page
        get_other_items(type_listing, items, element.text)
            
        # get next pages
        for page_number in range(2, int(max_page_number)+1):
            time.sleep(1)
            other_page = BeautifulSoup(requests.get(f"{MAIN_URL}{element['href']}/strona-{page_number}").text, features="lxml")
            get_other_items(other_page, items, element.text)

    
    # save to json file
    with open("emargo.json", "w", encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False)
    return

if __name__ == "__main__":
    main()