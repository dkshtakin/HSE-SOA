import logging
import threading
import random
from queue import SimpleQueue
from concurrent import futures
import google.protobuf.empty_pb2
import grpc
import time
import os

import mafia_pb2_grpc
import mafia_pb2


class GameSession():
    GAME_ROLES = ['Mafiosi', 'Detective', 'Villager']
    DISCUSSION_TIME = 2.0

    def __init__(self, users) -> None:
        self.users = users
        self.queues = {}
        for user in self.users:
            self.queues[user] = SimpleQueue()
        self.lock = threading.Lock()
        self.alive = set(users)
        self.day = 0
        self.mafia = None
        self.detective = None
        self.victim = None
        self.suspect = None
        self.detective_verdict = None
        self.response_count = 2
        self.next_cv = threading.Condition()
        self.votes = {}
        self.game_over = False

    def send(self, include_group, exclude_group, msg):
        for user, queue in self.queues.items():
            if user in include_group and user not in exclude_group:
                queue.put(mafia_pb2.ServerMessage(msg=msg))

    def send_including(self, group, msg):
        self.send(group, [], msg)

    def send_excluding(self, group, msg):
        self.send(self.queues.keys(), group, msg)

    def send_all(self, msg: str):
        self.send_including(self.queues.keys(), msg)

    def send_all_alive(self, msg: str):
        self.send_including(self.alive, msg)

    def start(self):
        roles = {}
        indexes = [i for i in range(len(self.users))]
        random.shuffle(indexes)
        self.mafia = self.users[indexes[0]]
        roles[self.mafia] = GameSession.GAME_ROLES[0]                 # 1 Mafiosi
        self.detective = self.users[indexes[1]]
        roles[self.detective] = GameSession.GAME_ROLES[1]             # 1 Detective
        for i in range(2, len(self.users)):
            roles[self.users[indexes[i]]] = GameSession.GAME_ROLES[2] # others are Villagers
        for username, queue in self.queues.items():
            queue.put(mafia_pb2.ServerMessage(msg=f'Your role is {roles[username]}'))
        predicate = lambda: self.response_count == 2
        while True:
            with self.next_cv:
                self.next_cv.wait_for(predicate)
            if self.game_over:
                return
            self.response_count = 0
            self.next_round()
            if self.game_over:
                return

    def next_round(self):
        if self.victim is not None:
            self.alive.remove(self.victim)
        self.send_all(f'Day {self.day}')
        if self.day != 0:
            self.queues[self.victim].put(mafia_pb2.ServerMessage(msg='You were killed by mafia'))
            self.send_all(f'The city is waking up... except {self.victim}')

        if len(self.alive) == 2:
            self.send_all(f'Game over, mafia won! {self.mafia} is the winner')
            return

        if self.day != 0:
            self.send_all_alive('Discussion')
            # Emulate discussion
            time.sleep(self.DISCUSSION_TIME)
            self.send_all_alive('Select action (continue/vote "user"):')
            predicate = lambda: self.response_count == len(self.alive)
            with self.next_cv:
                self.next_cv.wait_for(predicate)
            if self.game_over:
                return
            self.response_count = 0

        if self.votes:
            target = sorted(self.votes.items(), key = lambda item: item[1])[-1][0]
            self.alive.remove(target)
            self.send_all(f'{target} was choosen for execution')
            if target == self.mafia:
                self.send_all(f'Game over, villagers won!')
                return
            if len(self.alive) == 2:
                self.send_all(f'Game over, mafia won! {self.mafia} is the winner')
                return
            self.votes = {}

        self.send_all('The city falls asleep...')

        if self.detective in self.alive:
            suspects = ", ".join(filter(lambda x:
                x in self.alive and x != self.detective, self.users))
            self.queues[self.detective].put(mafia_pb2.ServerMessage(
                msg=f'Which of the players will be checked by detective: {suspects}?'))
        else:
            self.response_count += 1

        victims = ", ".join(filter(lambda x: x in self.alive and x != self.mafia, self.users))
        self.queues[self.mafia].put(mafia_pb2.ServerMessage(
            msg=f'Who will be the victim: {victims}?'))

        self.day += 1

    def choose_victim(self, user, victim):
        with self.lock:
            if user != self.mafia:
                return 1, 'Only mafia can choose victims'
            victims = filter(lambda x: x in self.alive and x != self.mafia, self.users)
            if victim not in victims:
                return 1, 'Please choose correct victim'
            self.victim = victim
            self.response_count += 1
            if self.response_count == 2:
                with self.next_cv:
                    self.next_cv.notify()
        return 0, 'OK'

    def choose_suspect(self, user, suspect):
        with self.lock:
            if user != self.detective:
                return 1, 'Only detective can choose suspects'
            suspects = filter(lambda x: x in self.alive and x != self.detective, self.users)
            if suspect not in suspects:
                return 1, 'Please choose correct suspect'
            self.suspect = suspect
            self.response_count += 1
            msg = 'Mafia' if suspect == self.mafia else 'Villager'
            if self.response_count == 2:
                with self.next_cv:
                    self.next_cv.notify()
        return 0, msg

    def skip_vote(self, username):
        with self.lock:
            self.send_excluding([username], f'{username} skipped vote')
            self.response_count += 1
            if self.response_count == len(self.alive):
                with self.next_cv:
                    self.next_cv.notify()

    def vote_for(self, username, target):
        with self.lock:
            if target not in self.alive:
                return 1, 'Please choose correct target'

            self.send_excluding([username], f'{username} voted against {target}')

            if target not in self.votes:
                self.votes[target] = 0
            self.votes[target] += 1

            self.response_count += 1
            if self.response_count == len(self.alive):
                with self.next_cv:
                    self.next_cv.notify()
        return 0, 'OK'

    def publish_detective_verdict(self, username, verdict):
        with self.lock:
            self.detective_verdict = verdict
            self.send_all_alive(f'Detective {self.detective} announces that mafia is {verdict}')

    def disconnect_user(self, username):
        with self.lock:
            self.response_count += 1
            self.game_over = True
            self.send_all(f'Game over, user "{username}" left lobby')


class MafiaGame(mafia_pb2_grpc.MafiaServicer):
    MIN_PLAYERS=4

    def __init__(self) -> None:
        super().__init__()
        self.waiters = 0
        self.queues = {}
        self.in_game = set()
        self.lock = threading.Lock()
        self.sessions = {}
        self.session_ids = {}
        self.session_counter = 0

    @staticmethod
    def is_valid(username):
        if not username:
            return False
        if len(username) == 0:
            return False
        if ' ' in username:
            return False
        return True

    def Login(self, request, context):
        username = request.username
        if not MafiaGame.is_valid(username):
            return mafia_pb2.LoginResponse(err_code=1, msg=f'Incorrect username "{username}"!')
        if username in self.queues:
            return mafia_pb2.LoginResponse(err_code=1, msg=f'User {username} already exists!')
        with self.lock:
            users = []
            for user, queue in self.queues.items():
                if user not in self.in_game:
                    users.append(user)
                    queue.put(mafia_pb2.ServerMessage(msg=f'New user "{username}" connected'))
        return mafia_pb2.LoginResponse(err_code=0,
                                       msg=f'Succesfully registered as {username}',
                                       users=users)

    def ReLogin(self, request, context):
        username = request.username
        if username not in self.queues:
            return mafia_pb2.LoginResponse(err_code=1,
                                           msg=f'User {username} does not exist, use Login!')
        with self.lock:
            self.in_game.remove(username)
            users = []
            for user, queue in self.queues.items():
                if username != user and user not in self.in_game:
                    users.append(user)
                    queue.put(mafia_pb2.ServerMessage(msg=f'User "{username}" reconnected'))
            self.waiters += 1
            if self.waiters >= MafiaGame.MIN_PLAYERS:
                self.start_game()
        return mafia_pb2.LoginResponse(err_code=0,
                                       msg=f'Succesfully relogined as {username}',
                                       users=users)

    def GetMessages(self, request, context):
        username = request.username
        queue = SimpleQueue()
        with self.lock:
            self.waiters += 1
            self.queues[username] = queue
            if self.waiters >= MafiaGame.MIN_PLAYERS:
                self.start_game()

        def disconnect_callback():
            with self.lock:
                if username in self.queues:
                    self.queues.pop(username)
                if username not in self.in_game:
                    self.waiters -= 1
                    for _, queue in self.queues.items():
                        queue.put(mafia_pb2.ServerMessage(msg=f'User "{username}" disconnected'))
                else:
                    self.sessions[self.session_ids[username]].disconnect_user(username)
                    self.in_game.remove(username)

        context.add_callback(disconnect_callback)
        while True:
            msg = queue.get()
            yield msg
            if msg.msg.startswith('Starting'):
                self.lock.acquire()
                queue = self.sessions[self.session_ids[username]].queues[username]
                self.lock.release()
            elif msg.msg.startswith('Game over'):
                self.lock.acquire()
                queue = self.queues[username]
                self.lock.release()

    def GetLobby(self, request, context):
        users = self.sessions[request.session_id].users
        return mafia_pb2.GetLobbyResponse(users=users)

    def ChooseVictim(self, request, context):
        username = request.username
        with self.lock:
            err_code, msg = self.sessions[request.session_id].choose_victim(
                username, request.victim)
        return mafia_pb2.ServerResponse(err_code=err_code, msg=msg)

    def ChooseSuspect(self, request, context):
        username = request.username
        with self.lock:
            err_code, msg = self.sessions[request.session_id].choose_suspect(
                username, request.suspect)
        return mafia_pb2.ServerResponse(err_code=err_code, msg=msg)

    def SkipVote(self, request, context):
        username = request.username
        with self.lock:
            self.sessions[request.session_id].skip_vote(username)
        return google.protobuf.empty_pb2.Empty()

    def PublishDetectiveVerdict(self, request, context):
        username = request.username
        with self.lock:
            self.sessions[request.session_id].publish_detective_verdict(username, request.mafia)
        return google.protobuf.empty_pb2.Empty()

    def VoteFor(self, request, context):
        username = request.username
        with self.lock:
            err_code, msg = self.sessions[request.session_id].vote_for(
                username, request.target)
        return mafia_pb2.ServerResponse(err_code=err_code, msg=msg)

    def start_game(self):
        users = list(self.queues.keys())
        session_users = list(filter(lambda x: x not in self.in_game, users))
        self.sessions[self.session_counter] = GameSession(session_users)
        session_thread = threading.Thread(target=self.sessions[self.session_counter].start)
        session_thread.start()
        for user, queue in self.queues.items():
            if user in self.in_game:
                continue
            self.in_game.add(user)
            self.session_ids[user] = self.session_counter
            queue.put(mafia_pb2.ServerMessage(
                msg=f'Starting new session with {", ".join(session_users)};\
                session # {self.session_counter}'))
        self.session_counter += 1
        self.waiters = 0


def serve():
    addr = os.environ.get('MAFIA_SERVER_ADDRESS', 'server:50051')
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    mafia_pb2_grpc.add_MafiaServicer_to_server(MafiaGame(), server)
    server.add_insecure_port(addr)
    server.start()
    print("Server started, listening on " + addr)
    server.wait_for_termination()


if __name__ == '__main__':
    logging.basicConfig()
    serve()
