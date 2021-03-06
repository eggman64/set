from itertools import chain

from .. import messages, commands, board, net
from ..game import initial_state, update, find_set


def test_find_set():
    assert find_set(board.make([0, 1, 2])) == (0, 1, 2)


def test_update_unknown():
    s, c = update(initial_state(), 0, {'type': 'unknown-489850'})
    assert s == initial_state()
    assert not c


def test_no_game():
    game_messages = (
        messages.set_announced(1, [0, 1, 2]),
        messages.cards_wanted(1),
    )

    for m in game_messages:
        s, c = update(initial_state(), 0, m)
        assert s == initial_state()
        assert not c


def test_update_basic():
    s = initial_state()
    s, c = update(s, 0, messages.player_joined(1, 'alice'))
    assert s['players'][0]['name'] == 'alice'
    assert not s['game']

    s, c = update(s, 0, messages.player_joined(1, 'alice'))
    assert len(s['players']) == 1

    s, c = update(s, 0, messages.player_joined(2, 'bob'))
    assert len(s['players']) == 2
    assert c[0]['type'] == commands.DELAY
    assert c[0]['message']['max_id'] == 2

    _player_leaving(s, c)

    s, c = update(s, 0, c[0]['message'])
    assert c[0]['type'] == commands.GENERATE_RANDOM

    s, c = update(s, 0, c[0]['message_func'](0))
    assert s['game']
    _all_leaving(s, c)
    assert -1 not in chain(*s['game']['board'])
    set1 = (49, 53, 45)
    assert find_set(s['game']['board']) == set1
    assert c[0]['type'] == commands.BROADCAST

    s, c = update(s, 0, messages.set_announced(2, set1))
    assert s['players'][1]['points'] == 1
    assert all(card not in chain(*s['game']['board']) for card in set1)
    assert c[0]['message']['position'] == (0, 0)
    assert c[1]['message']['position'] == (0, 1)
    assert c[2]['message']['position'] == (3, 0)
    assert s['game']['future_cards'] == 3

    assert not board.is_full(s['game']['board'])
    s = _apply_delayed(s, c)
    assert board.is_full(s['game']['board'])

    no_set = (5, 33, 65)
    s, c = update(s, 0, messages.set_announced(2, no_set))
    assert s['players'][1]['points'] == 0

    before = s
    s, c = update(s, 0, messages.cards_wanted(1))
    s, c = update(s, 0, messages.cards_wanted(2))
    assert s == before
    assert c[0]['data']['type'] == net.CARDS_DENIED

    _finish_game(s)

    # keep playing until there are no more sets
    while find_set(s['game']['board']):
        set2 = find_set(s['game']['board'])
        s, c = update(s, 0, messages.set_announced(1, set2))

        s = _apply_delayed(s, c)

    s, c = update(s, 0, messages.cards_wanted(1))
    s, c = update(s, 0, messages.cards_wanted(2))
    assert board.size(s['game']['board']) == 15
    s = _apply_delayed(s, c)
    assert board.is_full(s['game']['board'])


def _finish_game(s):
    while find_set(s['game']['board']) or s['game']['deck']:
        assert not s['game']['game_over']

        set3 = find_set(s['game']['board'])
        if set3:
            s, c = update(s, 0, messages.set_announced(1, set3))
        else:
            s, c = update(s, 0, messages.cards_wanted(1))
            s, c = update(s, 0, messages.cards_wanted(2))

        if s['game']['game_over']:
            s = _apply_delayed(s, c)
            assert not s['game']
            return

        s = _apply_delayed(s, c)


def _apply_delayed(s, cmds):
    for c in cmds:
        if c['type'] == commands.DELAY:
            s, _ = update(s, 0, c['message'])
    return s


def _player_leaving(s, c):
    s, _ = update(s, 0, messages.player_left(1))
    assert len(s['players']) == 1

    s, c = update(s, 0, c[0]['message'])
    assert not c, '# of players dropped below 2 during countdown, no game'


def _all_leaving(s, c):
    s, _ = update(s, 0, messages.player_left(1))
    s, _ = update(s, 0, messages.player_left(2))
    assert not s['game']


def test_no_final_set():
    # no set after final deal of cards
    before = {
        'players': [],
        'game': {
            'deck': [9],
            'board': ((30, 75, -1), (5, 72, 2), (6, 42, 7), (48, 46, 51)),
            'future_cards': 1,
            'game_over': False,
            'started_at': 1539184988.226014,
        },
    }
    message = messages.card_dealt((0, 2))
    after, _ = update(before, 0, message)
    assert after['game']['game_over'], "game should end immediately"
