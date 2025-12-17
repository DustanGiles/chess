import chess
import chess.engine

engine = chess.engine.SimpleEngine.popen_uci(r"/usr/games/stockfish")
board = chess.Board()

result = engine.play(board, chess.engine.Limit(time=0.100))
board.push(result.move)
print(board)

engine.configure({"Skill Level": 7})

board = chess.Board()
result = engine.play(board, chess.engine.Limit(time=0.100))
board.push(result.move)
print(board)
 

engine.quit()