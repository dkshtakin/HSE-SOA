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
import pika

import tkinter as tk
from tkinter import simpledialog

from functools import partial

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

def get_msg(default):
    if AUTO:
        print(default)
        return default
    msg = simpledialog.askstring(title="Discussion", prompt="Your message:")
    return msg


class ChatListener(threading.Thread):
    def __init__(self, session_id):
        def callback(ch, method, properties, body):
            print(f'{body.decode()}')

        super().__init__()
        self.session_id = session_id
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange=f'session#{self.session_id}', exchange_type='fanout')
        result = self.channel.queue_declare(queue='', exclusive=True)
        self.queue_name = result.method.queue
        self.channel.queue_bind(exchange=f'session#{self.session_id}', queue=self.queue_name)
        self.channel.basic_consume(queue=self.queue_name, on_message_callback=callback,
                                    auto_ack=True)

    def run(self):
        try:
            self.channel.start_consuming()
        finally:
            pass

    def stop(self):
        def callback(self):
            self.channel.stop_consuming()
            self.channel.close()
            self.connection.close()

        self.connection.add_callback_threadsafe(partial(callback, self))
        self.join()


def LobbyListen(stub, username):
    session_id = None
    mafia = None
    detective_verdict = None
    is_mafia = False
    users = []
    for msg in stub.GetMessages(mafia_pb2.GetMessagesRequest(username=username)):
        print(msg.msg)
        if msg.msg.startswith('Your role is '):
            role = msg.msg[len('Your role is '):]
            if role == 'Mafiosi':
                is_mafia = True
        elif msg.msg == 'The city falls asleep...' and is_mafia:
            cl = ChatListener(session_id)
            cl.start()
            if not AUTO:
                root = tk.Tk()
                root.withdraw()
            while True:
                msg = get_msg(default='/continue')
                if msg is None or msg == '/continue':
                    cl.stop()
                    break
                elif len(msg) > 0:
                    stub.SendChatMessage(mafia_pb2.SendChatMessageRequest(username=username,
                                                                          session_id=session_id,
                                                                          msg=msg))
        elif msg.msg == 'Discussion':
            cl = ChatListener(session_id)
            cl.start()
            if not AUTO:
                root = tk.Tk()
                root.withdraw()
            while True:
                msg = get_msg(default='/continue')
                if msg is None or msg == '/continue':
                    cl.stop()
                    break
                elif msg == '/publish':
                    if mafia is not None:
                        stub.PublishDetectiveVerdict(
                            mafia_pb2.PublishDetectiveVerdictRequest(username=username,
                                                                     session_id=session_id,
                                                                     mafia=mafia))
                        msg = f'{username} announces that {mafia} is mafia!'
                        stub.SendChatMessage(mafia_pb2.SendChatMessageRequest(username=username,
                                                                              session_id=session_id,
                                                                              msg=msg))
                elif len(msg) > 0:
                    stub.SendChatMessage(mafia_pb2.SendChatMessageRequest(username=username,
                                                                          session_id=session_id,
                                                                          msg=msg))
        elif msg.msg.startswith('Select action'):
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
                        print(f'{suspect} is mafia')
                        mafia = suspect
                    else:
                        print(f'{suspect} is not mafia')
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
