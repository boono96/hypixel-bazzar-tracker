from tkinter import *
from tkinter import ttk

import matplotlib.pyplot as plt
import numpy as np
import datetime
from file_handeler import file_handeler

root = Tk()

frm1 = Frame(root)
frm1.pack(fill=BOTH, expand=1)
bazzar_static = file_handeler.load_json_file('bazzar_static_file.json')

canvas = Canvas(frm1)
canvas.pack(side=LEFT, fill=BOTH, expand=1)

scroll_bar = ttk.Scrollbar(frm1, orient=VERTICAL, command=canvas.yview)
scroll_bar.pack(side=RIGHT, fill=Y)

canvas.configure(yscrollcommand=scroll_bar.set)
canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

frm2 = Frame(canvas)

canvas.create_window((0, 0), window=frm2, anchor="nw")


# print(bazzar_static)
def graph_single(name, x, y):
    plt.plot(bazzar_static[name][x], bazzar_static[name][y])
    plt.title(name)
    plt.xlabel(x)
    plt.ylabel(y)
    plt.ticklabel_format(style='plain')
    plt.show()


def graph_couple(name, x1, y1, y2):
    bazzar_name_v = bazzar_static[name]
    tx = np.array(bazzar_static[x1][bazzar_name_v['start_time'][0]::]).astype('datetime64[ms]')
    plt.plot(tx, bazzar_name_v[y1], color="blue", label=y1)
    plt.plot(tx, bazzar_name_v[y2], color="red", label=y2)
    plt.title(name)
    plt.xlabel(x1)
    plt.legend()
    plt.xticks(rotation=30)
    plt.ticklabel_format(style='plain', axis='y')
    plt.show()


def graph_six(name, x, Y1, Y2, Y3, Y4, Y5, Y6):
    figure, axis = plt.subplots(2, 3, num=name)

    # y1 = 'sell_price', y2 = 'buy_price',
    # y3 = 'sell_order', y4 = 'buy_order',
    # y5 = 'sell_volume', y6 = 'buy_volume'

    bazzar_name_v = bazzar_static[name]
    time = np.array(bazzar_static[x][bazzar_name_v['start_time'][0]::]).astype('datetime64[ms]')

    axis[0, 0].plot(time, bazzar_name_v[Y1])
    axis[0, 0].set_title(Y1)

    axis[1, 0].plot(time, bazzar_name_v[Y2])
    axis[1, 0].set_title(Y2)

    axis[0, 1].plot(time, bazzar_name_v[Y3])
    axis[0, 1].set_title(Y3)

    axis[1, 1].plot(time, bazzar_name_v[Y4])
    axis[1, 1].set_title(Y4)

    axis[0, 2].plot(time, bazzar_name_v[Y5])
    axis[0, 2].set_title(Y5)

    axis[1, 2].plot(time, bazzar_name_v[Y6])
    axis[1, 2].set_title(Y6)

    for ax in axis.flat:
        ax.ticklabel_format(style='plain', axis='y')
        ax.tick_params(axis='x', rotation=45)

    # figure.tight_layout(pad=0.01)
    plt.subplots_adjust(left=0.043,
                        bottom=0.102,
                        right=0.976,
                        top=0.948,
                        wspace=0.262,
                        hspace=0.429)
    plt.show()


def show_stat(name):
    root3 = Tk()
    root3.title('stat')

    T = Text(root3, height=30, width=52)
    T.pack()
    bazzar_name = bazzar_static[name]
    time = datetime.datetime.fromtimestamp(bazzar_static['time'][-1] / 1000.0).strftime('%d-%m-%Y %H:%M:%S')
    text = f"product : {name}\n" \
           f"time : {time}\n" \
           f"sell price : {bazzar_name['sell_price'][-1]}\n" \
           f"buy price : {bazzar_name['buy_price'][-1]}\n" \
           f"sell volume : {bazzar_name['sell_volume'][-1]}\n" \
           f"buy volume : {bazzar_name['buy_volume'][-1]}\n" \
           f"sell order : {bazzar_name['sell_order'][-1]}\n" \
           f"buy order : {bazzar_name['buy_order'][-1]}\n" \
           f"sell/buy :\n" \
           f"   sell price/buy price : {(bazzar_name['sell_price'][-1]) / (bazzar_name['buy_price'][-1])}\n" \
           f"   sell volume/buy volume : {(bazzar_name['sell_volume'][-1]) / (bazzar_name['buy_volume'][-1])}\n" \
           f"   sell order/buy order : {(bazzar_name['sell_order'][-1]) / (bazzar_name['buy_order'][-1])}\n" \
           f"buy/sell :\n" \
           f"   buy price/sell price : {(bazzar_name['buy_price'][-1]) / (bazzar_name['sell_price'][-1])}\n" \
           f"   buy volume/sell volume : {(bazzar_name['buy_volume'][-1]) / (bazzar_name['sell_volume'][-1])}\n" \
           f"   buy order/sell order : {(bazzar_name['buy_order'][-1]) / (bazzar_name['sell_order'][-1])}\n"
    T.insert(END, text)
    root3.mainloop()


def subplot_two(name, x1, x2, y1, y2, y3, y4):
    figure, axis = plt.subplots(1, 2, num=name)
    bazzar_name_v = bazzar_static[name]
    if x1 == x2:
        time1 = np.array(bazzar_static[x1][bazzar_name_v['start_time'][0]::]).astype('datetime64[ms]')
        time2 = time1
    else:
        time1 = np.array(bazzar_static[x1][bazzar_name_v['start_time'][0]::]).astype('datetime64[ms]')
        time2 = np.array(bazzar_static[x2][bazzar_name_v['start_time'][0]::]).astype('datetime64[ms]')

    axis[0].plot(time1, bazzar_name_v[y1], color="blue")
    axis[0].plot(time1, bazzar_name_v[y2], color="red")
    axis[0].set_title(f"{y1} / {y2}")
    axis[0].legend([y1, y2])

    axis[1].plot(time2, bazzar_name_v[y3], color="blue")
    axis[1].plot(time2, bazzar_name_v[y4], color="red")
    axis[1].set_title(f"{y3} / {y4}")
    axis[1].legend([y3, y4])

    for ax in axis.flat:
        ax.ticklabel_format(style='plain', axis='y')
        ax.tick_params(axis='x', rotation=45)

    plt.subplots_adjust(left=0.043,
                        bottom=0.102,
                        right=0.976,
                        top=0.948,
                        wspace=0.262,
                        hspace=0.429)

    plt.show()


def subplot_three(name, x1, y1, y2, y3, y4, y5, y6):
    figure, axis = plt.subplots(1, 3, num=name)
    bazzar_name_v = bazzar_static[name]
    time = np.array(bazzar_static[x1][bazzar_name_v['start_time'][0]::]).astype('datetime64[ms]')

    axis[0].plot(time, bazzar_name_v[y1], color="blue")
    axis[0].plot(time, bazzar_name_v[y2], color="red")
    axis[0].set_title(f"{y1} / {y2}")
    axis[0].legend([y1, y2])

    axis[1].plot(time, bazzar_name_v[y3], color="blue")
    axis[1].plot(time, bazzar_name_v[y4], color="red")
    axis[1].set_title(f"{y3} / {y4}")
    axis[1].legend([y3, y4])

    axis[2].plot(time, bazzar_name_v[y5], color="blue")
    axis[2].plot(time, bazzar_name_v[y6], color="red")
    axis[2].set_title(f"{y5} / {y6}")
    axis[2].legend([y5, y6])

    for ax in axis.flat:
        ax.ticklabel_format(style='plain', axis='y')
        ax.tick_params(axis='x', rotation=45)

    plt.subplots_adjust(left=0.043,
                        bottom=0.102,
                        right=0.976,
                        top=0.948,
                        wspace=0.262,
                        hspace=0.429)

    plt.show()


def show_more(i):
    root4 = Tk()
    root4.title('menu3')

    Button(root4, text="price and order", padx=100, pady=20,
           command=lambda name=i, x1='time', x2='time', y1='sell_price', y2='buy_price', y3='sell_order',
                          y4='buy_order': subplot_two(name, x1, x2, y1, y2, y3, y4)).grid(
        row=0, column=0)

    Button(root4, text="price and volume", padx=100, pady=20,
           command=lambda name=i, x1='time', x2='time', y1='sell_price', y2='buy_price', y3='sell_volume',
                          y4='buy_volume': subplot_two(name, x1, x2, y1, y2, y3, y4)).grid(
        row=1, column=0)
    Button(root4, text="volume and order", padx=100, pady=20,
           command=lambda name=i, x1='time', x2='time', y1='sell_volume', y2='buy_volume', y3='sell_order',
                          y4='buy_order': subplot_two(name, x1, x2, y1, y2, y3, y4)).grid(
        row=0, column=1)
    Button(root4, text="all_multiline", padx=100, pady=20,
           command=lambda name=i, x1='time', y1='sell_price', y2='buy_price', y3='sell_order',
                          y4='buy_order',y5='sell_volume',y6='buy_volume': subplot_three(name, x1, y1, y2, y3, y4,y5,y6)).grid(
        row=1, column=1)

    root4.mainloop()


def button_menu_2(i):
    root2 = Tk()
    root2.title('menu2')

    Button(root2, text="sell/buy price", padx=100, pady=20,
           command=lambda name=i, x1='time', y1='sell_price', y2='buy_price': graph_couple(name, x1, y1, y2)).grid(
        row=0, column=0)
    Button(root2, text="sell/buy order", padx=100, pady=20,
           command=lambda name=i, x1='time', y1='sell_order', y2='buy_order': graph_couple(name, x1, y1, y2)).grid(
        row=1, column=0)
    Button(root2, text="sell/buy volume", padx=100, pady=20,
           command=lambda name=i, x1='time', y1='sell_volume', y2='buy_volume': graph_couple(name, x1, y1, y2)).grid(
        row=2, column=0)
    Button(root2, text="all", padx=100, pady=20,
           command=lambda name=i, x='time', y1='sell_price', y2='buy_price', y3='sell_order', y4='buy_order',
                          y5='sell_volume', y6='buy_volume': graph_six(name, x, y1, y2, y3, y4, y5, y6)).grid(row=0,
                                                                                                              column=1)
    Button(root2, text="show_stat", padx=100, pady=20,
           command=lambda name=i: show_stat(name)).grid(
        row=1, column=1)

    Button(root2, text="more", padx=100, pady=20,
           command=lambda name=i: show_more(name)).grid(
        row=2, column=1)

    root2.mainloop()


j = 0
for i in bazzar_static.keys():
    j += 1
    if i != 'time' and i != 'BAZAAR_COOKIE':
        Button(frm2, text=str(i), padx=100, pady=20, command=lambda x=i: button_menu_2(x)).grid(row=j, column=0)

root.mainloop()
