
from time import sleep
from hypixel_api_class import hypixel_api
import datetime


hypixel1 = hypixel_api()
bazzar_info = hypixel1.get_information(hypixel1.name_link_bazzar)

def main():
    # "BAZAAR_COOKIE": {
    #      "product_id": "BAZAAR_COOKIE",
    #      "sell_summary": [ ],
    #      "buy_summary": [ ],
    #      "quick_status": {
    #        "productId": "BAZAAR_COOKIE",
    #        "sellPrice": 0.0,
    #        "sellVolume": 0,
    #        "sellMovingWeek": 0,
    #        "sellOrders": 0,
    #        "buyPrice": 0.0,
    #        "buyVolume": 0,
    #        "buyMovingWeek": 0,
    #        "buyOrders": 0

    def update_price_loop():
        t = 0
        while True:
            bazzar_info = hypixel1.get_information(hypixel1.name_link_bazzar)
            if bazzar_info['success']:
                hypixel1.update_price(bazzar_info, 'bazzar_static_file.json')
            else:
                print("fail")
                sleep(60)
            print(f"success number: {str(t)}  {datetime.datetime.fromtimestamp(bazzar_info['lastUpdated']/1000).strftime('%Y-%m-%d %H:%M:%S')}")
            t += 1
            sleep(30)



    # hypixel1.write_file_json(hypixel1.create_dict_name(bazzar_info),'bazzar_static_file.json')
    update_price_loop()

#rerun the programe after errors
while True:
        try:
            main()
        except Exception as e:
            print(f"\n-----------------an Error occure-----------------\n ({e})")
            pass
        else:
            break

