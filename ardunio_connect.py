import serial

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

def connect_to_arduino(port, baud, timeout=1):
    ser = serial.Serial(port, baud, timeout=timeout)
    wait_for_string('ready', ser)
    return ser

def read_packet(ser):
    while True:
        raw = ser.read_until(expected=END_CHAR)
        if not raw:
            continue

        try:
            start_index = raw.index(START_CHAR)
        except ValueError:
            continue

        packet = raw[start_index:]
        if not packet.endswith(END_CHAR):
            continue

        return packet[1:-1].decode()

def send_packet(data, ser):
    ser.write(START_CHAR + bytes(data, 'ascii') + END_CHAR)

def wait_for_string(expected, ser):
    while True:
        packet = read_packet(ser)
        if packet == expected:
            return

def calibrate(ser):
    send_packet('calibrate', ser)
    wait_for_string('ready', ser)

def read_sensors(ser):
    send_packet('?states?', ser)
    packet = read_packet(ser)

    # Convert letters to numeric states
    raw_states = []
    for i in packet:
        if i == "n":
            raw_states.append(2)
        elif i == "s":
            raw_states.append(1)
        elif i == "z":
            raw_states.append(0)

    # Reorder according to led_mapping: logical → physical
    mapped_states = [0] * 64
    for logical_index in range(64):
        physical_index = led_mapping[logical_index]
        mapped_states[logical_index] = raw_states[physical_index]

    return mapped_states

def set_led(led_buffer, led_index, rgb):
    r, g, b = rgb
    start = led_mapping[led_index] * 3
    led_buffer[start:start+3] = [r, g, b]

def send_led_buffer(led_buffer, ser):
    for i in range(len(led_buffer)):
        if led_buffer[i] > 253:
            led_buffer[i] = 253
    send_packet("led values coming", ser)
    wait_for_string('awaiting', ser)
    message = bytes([0xFE]) + bytes(led_buffer) + bytes([0xFF])
    ser.write(message)

def led_update(ser):
    while True:
        states = read_sensors(ser)
        for i in range(len(states)):
            if states[i] == 2:
                set_led(led_buffer_01, i, (200, 200, 0))
            elif states[i] == 1:
                set_led(led_buffer_01, i, (0, 200, 200))

def change_param(param, val, ser):
    send_packet(param + ":" + str(val), ser)

def query_param(param, ser):
    send_packet("?" + param + "?", ser)
    return(read_packet(ser))