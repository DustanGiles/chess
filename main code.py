import serial
import time
from gpiozero import Button
import threading
import chess
import ardunio_connect
import chess.engine

engine = chess.engine.SimpleEngine.popen_uci(r"/usr/games/stockfish")

engine.configure({"Skill Level": 20})

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

# ----------------------
# LED Color Variables
# ----------------------
COLOR_EMPTY = (0, 0, 0)        
COLOR_WHITE = (0, 0, 250)
COLOR_WHITE_DIMMED = (0, 0, 20)
COLOR_BLACK = (0, 250, 0)  
COLOR_BLACK_DIMMED = (0, 20, 0)
COLOR_WHITE_SQUARES = (160, 160, 160)    
COLOR_BLACK_SQUARES = (10, 10, 10)
COLOR_HIGHLIFT = (0, 150, 255)   
COLOR_LEGAL_MOVE = (255, 255, 0)  
COLOR_CAPTURE = (255, 0, 0)   
COLOR_ERROR = (255, 50, 50)   


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

            if r != 0 or g != 0 or b != 0:   # only override non-empty
                out[start:start+3] = [r, g, b]

    return out



def infer_move(before_state, after_state):

    removed = []
    added = []

    if before_state == after_state: # Well, thats not much of a move...
        return "nomove"
        
    for square in range(len(before_state)):
        if before_state[square] != 0 and after_state[square] == 0: # If piece was there and is now not there:
            removed.append((square, before_state[square])) # Add square and piece color to removed pieces

        if before_state[square] == 0 and after_state[square] != 0: # If piece was not there and is there:
            added.append((square, after_state[square])) # Add square and piece color to added pieces
    
    # Normal Move
    if len(removed) == 1 and len(added) == 1: # Exactly 1 piece was added and removed
        if removed[0][1] == added[0][1]: # If added and removed square are the same color:

            from_square = index_to_alg(removed[0][0])
            to_square = index_to_alg(added[0][0])

            print(f"Move: {from_square} - {to_square}")
            return from_square+to_square

    # Capture
    elif len(removed) == 1 and len(added) == 0: # 1 piece removed and none added:
        for square in range(len(before_state)): # Check all squares
            if before_state[square] != 0 and before_state[square] != removed[0][1]: # If square was occupied and of not removed square color:
                if after_state[square] == removed[0][1]: # If this square now is the color of picked up piece:
                    
                    from_square = index_to_alg(removed[0][0])
                    to_square = index_to_alg(square)
                    
                    print(f"Capture: {from_square} - {to_square}")
                    return from_square+to_square

    return "invalid" # No valid move found
    
def index_to_alg(board_index):
    return chess.square_name(board_index)

def alg_to_index(alg):
    return chess.parse_square(alg)

def find_lifted_pieces(before_state, after_state):
    removed = []

    for square in range(len(before_state)):
        if before_state[square] != 0 and after_state[square] == 0: # If piece was there and is now not there:
            removed.append((square, before_state[square])) # Add square and piece color to removed pieces

    return removed

def board_to_state(board):
    state = []
    for sq in range(64):
        piece = board.piece_at(sq)
        if piece is None:
            state.append(0)
        elif piece.color:   # True = white
            state.append(1)
        else:               # False = black
            state.append(2)
    return state

def setup():
    global arduino, button
    arduino = ardunio_connect.connect_to_arduino(arduino_port, baud_rate)

    print(ardunio_connect.query_param("north_thresh", arduino))
    ardunio_connect.change_param("north_thresh", 10, arduino)
    print(ardunio_connect.query_param("south_thresh", arduino))
    ardunio_connect.change_param("south_thresh", 25, arduino)
    # ardunio_connect.change_param("bias", 5, arduino)
    # print(ardunio_connect.query_param("bias", arduino))
    print("average")
    print(ardunio_connect.query_param("average", arduino))

    button = Button("GPIO26")



def piece_position_highlights(current_state, turn_highlighting):
    for i in range(len(current_state)):
        if current_state[i] == 2:
            if board.turn == chess.BLACK and turn_highlighting:
                set_led_layer(layer_piece_positions, i, COLOR_BLACK)
            else:
                set_led_layer(layer_piece_positions, i, COLOR_BLACK_DIMMED)
        elif current_state[i] == 1:
            if board.turn == chess.WHITE and turn_highlighting:  # white to move
                set_led_layer(layer_piece_positions, i, COLOR_WHITE)
            else:
                set_led_layer(layer_piece_positions, i, COLOR_WHITE_DIMMED)
        else: 
            set_led_layer(layer_piece_positions, i, COLOR_EMPTY)

def show_move_diff(expected_state, actual_state):
    """Lights LEDs where pieces must be moved: 
       +1 = place piece (red), -1 = remove piece (green).
    """
    other_player_moves.clear()

    for i in range(NUM_LEDS):
        diff = expected_state[i] - actual_state[i]

        if diff > 0:
            set_led_layer(other_player_moves, i, COLOR_LEGAL_MOVE)   # needs a piece
        elif diff < 0:
            set_led_layer(other_player_moves, i, COLOR_HIGHLIFT)   # piece should be removed

    ardunio_connect.send_led_buffer(compose_layers(layers), arduino)


def wait_for_board_state(target_state):
    """Blocks until sensors match the expected target_state."""
    while True:
        if ardunio_connect.read_sensors(arduino) == target_state:
            return
        time.sleep(0.05)

setup()

board = chess.Board()


def on_button_press():
    global button_pressed
    button_pressed = True



button.when_pressed = on_button_press

button_pressed = False
ready_for_button = False
waiting_for_corrections = False

removed = []

old_led_buffer = led_buffer_01

highlighted_squares = []

layer_piece_positions = LEDLayer()
layer_highlights = LEDLayer()
base = LEDLayer()
effects = LEDLayer()
other_player_moves = LEDLayer()


layers = [
    base,
    
    layer_piece_positions,
    layer_highlights,
    other_player_moves,
    effects,
    
]

# Todo:
# Detect pieces being lifted and show legal legal moves
# - done
# Add waiting for board setup before start
# - done
# Add handling for when an illegal move is made
# - done
# Add en-pasent, castling and promotion
# Add win condition checking
# Led stuff (efffects, piece highlighting)
# - piece highlighting done
# Intergrate chess engine
# Add online play

for i in range(NUM_LEDS):
    row = i // 8
    col = i % 8
    if (row + col) % 2 == 0:
        set_led_layer(base, i, COLOR_WHITE_SQUARES)   # dark square
    else:
        set_led_layer(base, i, COLOR_BLACK_SQUARES)  # light square

ardunio_connect.send_led_buffer(compose_layers(layers), arduino)

time.sleep(2)





# Wait until sensors match board position
target_state = board_to_state(board)

old_state = ardunio_connect.read_sensors(arduino)

old_state_for_lift_detection = ardunio_connect.read_sensors(arduino)

ready = False
while not ready:
    current_state = ardunio_connect.read_sensors(arduino)
    
    piece_position_highlights(current_state, False)
    
    ardunio_connect.send_led_buffer(compose_layers(layers), arduino)


    # Compare all 64 squares
    if current_state == target_state:
        ready = True

old_state = ardunio_connect.read_sensors(arduino)

old_state_for_lift_detection = ardunio_connect.read_sensors(arduino)



print("ready")

while not board.is_checkmate():

    if board.turn == chess.WHITE:

        current_state = ardunio_connect.read_sensors(arduino)

        piece_position_highlights(current_state, True)

        ardunio_connect.send_led_buffer(compose_layers(layers), arduino)

        for square in range(len(old_state_for_lift_detection)):
            # Piece lifted
            if old_state_for_lift_detection[square] != 0 and current_state[square] == 0:
                piece = board.piece_at(square)
                # Skip if no piece present in the board model at that square
                if piece is None:
                    continue

                # Only highlight if the lifted piece belongs to the side to move
                if piece.color == board.turn:
                    legal_moves = list(board.legal_moves)
                    set_led_layer(layer_highlights, square, COLOR_HIGHLIFT)  # lifted square = blue
                    highlighted_squares.append(square)

                    for move in legal_moves:
                        if move.from_square == square:
                            highlighted_squares.append(move.to_square)
                            # highlight legal destination squares
                            if board.is_capture(move):
                                set_led_layer(layer_highlights, move.to_square, COLOR_CAPTURE)  # capture = red
                            else:
                                set_led_layer(layer_highlights, move.to_square, COLOR_LEGAL_MOVE) # normal move = green

            # Piece placed
            elif old_state_for_lift_detection[square] == 0 and current_state[square] != 0:
                layer_highlights.clear()

        old_state_for_lift_detection = current_state
        
        if button_pressed:
            button_pressed = False
            if not waiting_for_corrections:
                move = infer_move(old_state, current_state)
                if move != "nomove": # there was something that moved:
                    if move == "invalid": # it could not be infered
                        print("cannot infer move, please put pieces to previous locations")
                        for i in range(len(old_state)):
                            if old_state[i] != 0:
                                set_led_layer(effects, i, COLOR_ERROR)
                        waiting_for_corrections = True
                        print(old_state)
                        print(current_state)
                    else: # Found move
                        print(move)
                        try:
                            board.push_uci(move)
                            print(board)
                            old_state = current_state
                        except:
                            for i in range(len(old_state)):
                                if old_state[i] != 0:
                                    set_led_layer(effects, i, COLOR_ERROR)
                            print("illegal move")
                            print(old_state)
                            print(current_state)

            elif current_state == old_state:
                print("pieces have been corrected, moving on")
                effects.clear()
                waiting_for_corrections = False

    elif board.turn == chess.BLACK:
                
        piece_position_highlights(current_state, True)

        temp_board = board

        engine_choice = engine.play(board, chess.engine.Limit(time=0.1))

        temp_board.push(engine_choice.move)

        expected_state = board_to_state(temp_board)
        actual_state   = ardunio_connect.read_sensors(arduino)

        # Show guidance
        show_move_diff(expected_state, actual_state)

        # Wait until user has physically made the move
        wait_for_board_state(expected_state)

        # Clear LED hints and commit
        other_player_moves.clear()
        ardunio_connect.send_led_buffer(compose_layers(layers), arduino)

        board = temp_board

        old_state = ardunio_connect.read_sensors(arduino)


        print(board)
        


print("la fin")