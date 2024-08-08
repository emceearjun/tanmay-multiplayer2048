from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_cors import CORS
import logic
import uuid

# TODO
# Display modal only for player if their board is full to reset it - not with reloading, separate function to reset from server
# Display which player has won in center modal
# Delete rooms without any players - maybe also timeout if 2 people do not join - if person leaves room as well

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True, async_handlers=True)
app.secret_key = '06ae106f5b4e740059c97782'
client_rooms = {}
game_rooms = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/game/<room_id>')
def game(room_id):
    if room_id not in game_rooms or len(game_rooms[room_id]) == 2:
        return redirect(url_for('index'))
    response = make_response(render_template('game.html', room_id=room_id))
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/create', methods=['GET', 'POST'])
def create():
    room_id = str(uuid.uuid4()).replace("-", "")
    game_rooms[room_id] = {}
    return redirect(url_for('game', room_id=room_id))

@app.route('/join', methods=['GET', 'POST'])
def join():
    room_id = request.form.get('room_id')
    return redirect(url_for('game', room_id=room_id))

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data['room_id']
    if room_id in game_rooms:
        join_room(room_id)
        client_rooms[request.sid] = room_id
        game = logic.reset()
        game_rooms[room_id][request.sid] = {
            'mat': game[0],
            'score': game[1]
        }
        emit('joined', {'room_id': room_id,
                        'game': game_rooms[room_id]},
                        room=room_id)
        ids = iter(game_rooms[room_id])
        emit('show_score', {'player': 0}, to=next(ids))
        if len(game_rooms[room_id]) == 2:
            emit('show_score', {'player': 1}, to=next(ids))

@socketio.on('update')
def update(data):
    key = data['key']
    room_id = data['room_id']
    player = 0 if next(iter(game_rooms[room_id])) == request.sid else 1
    mat = game_rooms[room_id][request.sid]['mat']
    score = game_rooms[room_id][request.sid]['score']
    next_mat, points = logic.keys[key](mat)
    if next_mat != mat:
        mat = next_mat
        score += points
        logic.addnum(mat)
        state = logic.state(mat)
        game_rooms[room_id][request.sid] = {'mat': mat, 'score': score}
        emit('updated', {'player': player, 'mat': mat, 'score': score}, room=room_id)
        if state != 'playing':
            if state == 'stuck':
                emit('show_popup', {'player': player, 'state': state}, to=request.sid)
            else:
                emit('show_popup', {'player': player,
                                    'state': 'loss'}, to=request.sid)
                emit('show_popup', {'player': player,
                                    'state': 'loss'},
                                    to=game_rooms[room_id][list(game_rooms[room_id])[1-player]])

@socketio.on('reset')
def reset(data):
    room_id = data['room_id']
    player = 0 if next(iter(game_rooms[room_id])) == request.sid else 1
    game = logic.reset()
    game_rooms[room_id][request.sid] = {
        'mat': game[0],
        'score': game[1]
    }
    emit('updated', {'player': player, 'mat': game[0], 'score': 0}, room=room_id)

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    room_id = client_rooms[request.sid]
    del client_rooms[request.sid]
    del game_rooms[room_id][request.sid]
    if not len(game_rooms[room_id]):
        del game_rooms[room_id]
        print(f'Deleted room: {room_id}')
    else:
        # for player in range(2):
        #     emit('updated', {'player': player,
        #                      'mat': [[0] * 4 for _ in range(4)],
        #                      'score': 0,
        #                      'state': ''}, room=room_id)
        # game = logic.reset()
        player = 0 if next(iter(game_rooms[room_id])) == request.sid else 1
        emit('updated', {'player': player,
                         'mat': [[0] * 4 for _ in range(4)],
                         'score': 0,
                         'state': ''}, room=room_id)
        remaining_player = list(game_rooms[room_id])[0]
        # game_rooms[room_id][remaining_player] = {
        #         'mat': game[0],
        #         'score': game[1]
        # }
        emit('show_score', {'player': 0}, to=remaining_player)
        emit('remove_listener', to=remaining_player)
    print(f'Client disconnected: {request.sid}')

@socketio.on('message')
def handle_message(message):
    emit('message', message, broadcast=True)

# if __name__ == '__main__':
#     socketio.run(app)