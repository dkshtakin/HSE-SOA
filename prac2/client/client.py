from __future__ import print_function

import mafia_pb2
import mafia_pb2_grpc

import grpc
import logging
import google.protobuf.json_format
import threading
import time
import os
import sys
import random

import google.protobuf.empty_pb2

DISCUSSION_TIME = 3.0
AUTO = True if len(sys.argv) > 1 else False

def is_valid(username):
    if not username:
        return False
    if len(username) == 0:
        return False
    if ' ' in username:
        return False
    return True

def get_input(default):
    if AUTO:
        print(default)
        return default
    return input()

def LobbyListen(stub, username):
    session_id = None
    mafia = None
    detective_verdict = None
    is_mafia = False
    users = []
    for msg in stub.GetMessages(mafia_pb2.GetMessagesRequest(username=username)):
        print(msg.msg)
        if msg.msg == 'Discussion':
            if mafia is not None:
                print(f'Do you want to announce that {mafia} is mafia? (yes/other)')
                action = get_input(default='yes')
                if action == 'yes':
                    stub.PublishDetectiveVerdict(
                        mafia_pb2.PublishDetectiveVerdictRequest(username=username,
                                                                 session_id=session_id,
                                                                 mafia=mafia))
        if msg.msg.startswith('Select action'):
            while True:
                action = get_input(default=
                                   ('continue' if detective_verdict is None or is_mafia
                                    else f'vote {detective_verdict}'))
                if action == 'continue':
                    stub.SkipVote(mafia_pb2.SkipVoteRequest(username=username,
                                                            session_id=session_id))
                    break
                elif action.startswith('vote '):
                    target = action[len('vote '):]
                    response = stub.VoteFor(mafia_pb2.VoteForRequest(username=username,
                                                                     session_id=session_id,
                                                                     target=target))
                    if response.err_code == 0:
                        break
                    print(response.msg)
                print('!Enter correct action:')
        elif msg.msg.startswith('Who'):
            while True:
                is_mafia = True
                victim = get_input(default=random.choice(users))
                response = stub.ChooseVictim(mafia_pb2.ChooseVictimRequest(username=username,
                                                                           session_id=session_id,
                                                                           victim=victim))
                if response.err_code == 0:
                    break
                print(response.msg)
        elif msg.msg.startswith('Which'):
            while True:
                suspect = get_input(default=random.choice(users))
                response = stub.ChooseSuspect(mafia_pb2.ChooseSuspectRequest(username=username,
                                                                            session_id=session_id,
                                                                            suspect=suspect))
                if response.err_code == 0:
                    if response.msg == 'Mafia':
                        mafia = suspect
                    break
                print(response.msg)
        elif msg.msg.startswith('Game over'):
            print()
            response = stub.ReLogin(mafia_pb2.LoginRequest(username=username))
            print(response.msg)
            print(f'Lobby: {", ".join(list(response.users) + [username])}')
            if response.err_code != 0:
                return
        elif msg.msg.startswith('Starting'):
            session_id = int(msg.msg.split(' ')[-1])
            mafia = None
            detective_verdict = None
            is_mafia = False
            response = stub.GetLobby(mafia_pb2.GetLobbyRequest(username=username,
                                                               session_id=session_id))
            users = response.users
        elif msg.msg.startswith('Detective'):
            detective_verdict = msg.msg[msg.msg.find(('mafia is ')) + len('mafia is '):]

def run():
    while True:
        print('Enter server address (format hostname:port):')
        addr = get_input(default=os.environ.get('MAFIA_SERVER_ADDRESS', '0.0.0.0:50051'))
        try:
            with grpc.insecure_channel(addr) as channel:
                stub = mafia_pb2_grpc.MafiaStub(channel)

                username = None
                while not is_valid(username):
                    print('Enter username (it must be unique and without extra spaces): ', end='')
                    username = get_input(default=sys.argv[1] if AUTO else None)
                response = stub.Login(mafia_pb2.LoginRequest(username=username))
                print(response.msg)

                if response.err_code == 0:
                    print(f'Lobby: {", ".join(list(response.users) + [username])}')
                    lobby_thread = threading.Thread(target=LobbyListen, args=(stub, username))
                    lobby_thread.start()
                    lobby_thread.join()

        except Exception as exception:
            print(exception)


if __name__ == '__main__':
    logging.basicConfig()
    run()
