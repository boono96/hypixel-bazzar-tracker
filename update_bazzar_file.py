from hypixel_api_class import hypixel_api


hypixel = hypixel_api(65,4,8774)

bazzar_info = hypixel.get_information(hypixel.name_link_bazzar)
hypixel.update_price(bazzar_info,'bazzar_static_file.json')
hypixel.update_dict_key(bazzar_info,'bazzar_static_file.json')
# hypixel.create_start_time('bazzar_static_file.json',bazzar_info)