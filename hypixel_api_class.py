import json
import requests
from file_handeler import file_handeler


class hypixel_api(file_handeler):
    def __init__(self):
        self.name_link_bazzar = f"https://api.hypixel.net/skyblock/bazaar"

    # return in json format
    def get_information(self, link):
        r = requests.get(link)
        return r.json()

    def create_dict_name(self, information):
        dictinfo = {'time': []}
        for i in information['products'].values():
            dictinfo[i['quick_status']['productId']] = {'start_time':[9999, False], 'sell_price': [], 'buy_price': [],
                                                        'sell_order': []
                , 'buy_order': [], 'buy_volume': [], 'sell_volume': []}
        return dictinfo

    def update_dict_key(self, information, file):
        f = self.load_json_file(file)
        for i, j in information['products'].items():  # i = name ,j = values
            if i != 'time':
                if i in f:
                    print(f"{i} already exit")
                    pass
                else:
                    f[i['quick_status']['productId']] = {'start_time': [int, False], 'sell_price': [], 'buy_price': [],
                                                         'sell_order': [], 'buy_order': [], 'buy_volume': [],
                                                         'sell_volume': []}
        self.write_file_json(f, 'bazzar_static_file.json')

    def check_if_exit(self, list_info, item):

        for i in list_info.keys():  # i = name ,j = values
            if i != 'time':
                if item in list_info:
                    return True
                else:
                    return False

    def create_start_time(self, file, info):
        f = self.load_json_file(file)
        for i in f.keys():
            if i != 'time':
                if not f[i]['start_time'][1]:
                    f[i]['start_time'] = [f['time'].index(info['lastUpdated']), True]
        print(f)
        self.write_file_json(f, file)

    def create_bazzar_file(self, information, file):
        with open(file, 'w') as f:
            json.dump(self.create_dict_name(information), f)

    def update_price(self, info, file, ):
        f = self.load_json_file(file)
        f['time'].append(info['lastUpdated'])
        for i in info['products'].values():
            f[i['quick_status']['productId']]['sell_price'].append(
                float("{:.2f}".format(i['quick_status']['sellPrice'])))
            f[i['quick_status']['productId']]['buy_price'].append(float("{:.2f}".format(i['quick_status']['buyPrice'])))
            f[i['quick_status']['productId']]['sell_order'].append(
                float("{:.2f}".format(i['quick_status']['sellOrders'])))
            f[i['quick_status']['productId']]['buy_order'].append(
                float("{:.2f}".format(i['quick_status']['buyOrders'])))
            f[i['quick_status']['productId']]['buy_volume'].append(
                float("{:.2f}".format(i['quick_status']['buyVolume'])))
            f[i['quick_status']['productId']]['sell_volume'].append(
                float("{:.2f}".format(i['quick_status']['sellVolume'])))

        with open(file, 'w') as c:
            json.dump(f, c)

    def get_static_data(self, names):
        info = self.load_json_file('bazzar_static_file.json')
        return info[names]
