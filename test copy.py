import serial
import time
from gpiozero import Button
import threading
import chess
import ardunio_connect

arduino_port = '/dev/ttyUSB0'
baud_rate = 500000
START_CHAR = b'<'
END_CHAR = b'>'

led_mapping = [
    28, 24, 20, 16, 15, 14, 13, 12,
    29, 25, 21, 17, 11, 10,  9,  8,
    30, 26, 22, 18,  7,  6,  5,  4,
    31, 27, 23, 19,  3,  2,  1,  0,
    32, 33, 34, 35, 51, 55, 59, 63,
    36, 37, 38, 39, 50, 54, 58, 62,
    40, 41, 42, 43, 49, 53, 57, 61,
    44, 45, 46, 47, 48, 52, 56, 60 
]


led_buffer_01 = [0, 0, 0] * 64

NUM_LEDS = 64

class LEDLayer:
    def __init__(self):
        self.buffer = [0, 0, 0] * NUM_LEDS
        self.enabled = True

    def clear(self):
        self.buffer = [0, 0, 0] * NUM_LEDS

def set_led_layer(layer, led_index, rgb):
    r, g, b = rgb
    start = led_mapping[led_index] * 3
    layer.buffer[start:start+3] = [r, g, b]

def compose_layers(layers):
    out = [0, 0, 0] * 64

    for layer in layers:  # bottom → top
        if not layer.enabled:
            continue

        for i in range(64):
            start = i * 3
            r, g, b = layer.buffer[start:start+3]

            # Only override if this layer has a non-zero color
            if r != 0 or g != 0 or b != 0:
                out[start:start+3] = [r, g, b]

    return out







def setup():
    global arduino, button
    arduino = ardunio_connect.connect_to_arduino(arduino_port, baud_rate)

    print(ardunio_connect.query_param("sensitivity", arduino))
    ardunio_connect.change_param("sensitivity", 22, arduino)
    print(ardunio_connect.query_param("sensitivity", arduino))
    ardunio_connect.change_param("bias", 12, arduino)
    print(ardunio_connect.query_param("bias", arduino))
    print("average")
    print(ardunio_connect.query_param("average", arduino))

    button = Button("GPIO26")

    time.sleep(1)

    print("waiting")

layer_piece_positions = LEDLayer()
layer_highlights = LEDLayer()
layer_lift = LEDLayer()


layers = [
    layer_piece_positions,
    layer_highlights,
    layer_lift,
]

setup()


set_led_layer(layer_lift, 2, (200,0,0))
set_led_layer(layer_piece_positions, 2, (0,0,200))

ardunio_connect.send_led_buffer(compose_layers(layers), arduino)