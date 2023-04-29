from xml_marshaller import xml_marshaller
from pympler import asizeof
from functools import partial
from io import BytesIO

import json
import jsonpickle
import logging
import msgpack
import socket
import os
import person_pb2
import pickle
import timeit
import yaml
import struct
import threading

import avro.schema
from avro.io import DatumReader, DatumWriter, BinaryEncoder, BinaryDecoder

logging.basicConfig(level=logging.INFO)

class Person:
    def __init__(self, d={}):
        if d:
            self.__dict__ = d
            return
        self.name = "Bob"
        self.surname = "Aaron"
        self.age = 42
        self.hobby = ["reading", "skydiving", "knitting", "enduro"]
        self.info = {"nickname": ["coolbob", "BobTheWinner", "callmebob"]}
        self.score = 99.9913
        self.data = [i for i in range(42)]
    
BOB = Person()
ITERATIONS = 1000
PRECISION = 5

def convert_to_ms(s: float):
    return s * 1000


def native_ser(object):
    return pickle.dumps(object)

def native_des(object):
    return pickle.loads(object)

def xml_ser(object):
    return xml_marshaller.dumps(object)

def xml_des(object):
    return xml_marshaller.loads(object)

def json_ser(object):
    return jsonpickle.encode(object)

def json_des(object):
    return jsonpickle.decode(object)

def protobuf_ser(object):
    return object.SerializeToString()

def protobuf_des(object):
    obj = person_pb2.Person()
    obj.ParseFromString(object)
    return obj

def avro_ser(object, schema):
    data = BytesIO()
    encoder = BinaryEncoder(data)
    writer = DatumWriter(schema)
    writer.write(object.__dict__, encoder)
    return data.getvalue()
    
def avro_des(object, schema):
    data = BytesIO(object)
    decoder = BinaryDecoder(data)
    reader = DatumReader(schema)
    return Person(reader.read(decoder))

def yaml_ser(object):
    return yaml.dump(object)

def yaml_des(object):
    return yaml.load(object, Loader=yaml.Loader)

def msgpack_ser(object):
    return msgpack.packb(object.__dict__, use_bin_type=True)

def msgpack_des(object):
    return Person(msgpack.unpackb(object, raw=False))


def base_ser_des(object, size, format, ser_func, des_func):
    ser_time = convert_to_ms(timeit.Timer(partial(ser_func, object)).timeit(ITERATIONS) / ITERATIONS)
    object_ser = ser_func(object)
    size = asizeof.asizeof(object_ser)
    des_time = convert_to_ms(timeit.Timer(partial(des_func, object_ser)).timeit(ITERATIONS) / ITERATIONS)
    return f'{format} - {size} - {ser_time:.{PRECISION}f}ms - {des_time:.{PRECISION}f}ms'

def native_ser_des():
    return base_ser_des(BOB, asizeof.asizeof(BOB), 'NATIVE', native_ser, native_des)
    
def xml_ser_des():
    return base_ser_des(BOB, asizeof.asizeof(BOB), 'XML', xml_ser, xml_des)
   
def json_ser_des():
    return base_ser_des(BOB, asizeof.asizeof(BOB), 'JSON', json_ser, json_des)

def protobuf_ser_des():
    dummy = Person()
    Bob = person_pb2.Person()
    Bob.name = dummy.name
    Bob.surname = dummy.surname
    Bob.age = dummy.age
    Bob.hobby.extend(dummy.hobby)
    for key, value in dummy.info.items():
        Bob.info[key].nickname.extend(value)
    Bob.score = dummy.score
    Bob.data.extend(dummy.data)
    
    return base_ser_des(Bob, asizeof.asizeof(BOB), 'PROTOBUF', protobuf_ser, protobuf_des)

def avro_ser_des():
    json_schema = {
        "namespace": "prac1.avro",
        "type": "record",
        "name": Person.__name__,
        "fields": [
            {'name': 'name', 'type': 'string'},
            {'name': 'surname', 'type': 'string'},
            {'name': 'age', 'type': 'int'},
            {'name': 'hobby', 'type': {'type': 'array', 'items': 'string'}},
            {'name': 'info', 'type': {'type': 'map', 'values': {'type': 'array', 'items': 'string'}}},
            {'name': 'score', 'type': 'float'},
            {'name': 'data', 'type': {'type': 'array', 'items': 'int'}},
        ],
    }
    schema = avro.schema.parse(json.dumps(json_schema))
    return base_ser_des(BOB, asizeof.asizeof(BOB), 'AVRO', partial(avro_ser, schema=schema), partial(avro_des, schema=schema))

def yaml_ser_des():
    return base_ser_des(BOB, asizeof.asizeof(BOB), 'YAML', yaml_ser, yaml_des)
    
def msgpack_ser_des():
    return base_ser_des(BOB, asizeof.asizeof(BOB), 'MSGPACK', msgpack_ser, msgpack_des) 
    
TYPES = ['native', 'xml', 'json', 'protobuf', 'avro', 'yaml', 'msgpack', 'all']
TEST_FUNC = [
    native_ser_des,
    xml_ser_des,
    json_ser_des,
    protobuf_ser_des,
    avro_ser_des,
    yaml_ser_des,
    msgpack_ser_des
]

def unicast_listen(host, port, proxy_addr, proxy_port, test_type):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as unicast_sock:
        unicast_sock.bind((host, port))
        logging.info(f'listening on {host}:{port}')
        while True:
            data, addr = unicast_sock.recvfrom(1024)
            logging.info(f'Got {data} from {addr}')
            try:
                data = data.decode().strip('\n')
                assert data == 'get_result ' + TYPES[test_type]
                result = TEST_FUNC[test_type]()
                unicast_sock.sendto(result.encode(), (proxy_addr, proxy_port))
            except Exception as e:  
                logging.info(e)
                unicast_sock.sendto(str(e).encode(), (proxy_addr, proxy_port))


def multicast_listen(multicast_group, multicast_port, proxy_addr, proxy_port, test_type):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as multicast_sock:
        multicast_sock.bind(('', multicast_port))
        logging.info(f'listening on \'\':{multicast_port}')
        membership = struct.pack("4sL", socket.inet_aton(multicast_group), socket.INADDR_ANY)
        multicast_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        while True:
            data, addr = multicast_sock.recvfrom(1024)
            logging.info(f'Got {data} from {addr}')
            try:
                data = data.decode().strip('\n')
                assert data == 'get_result all'
                result = TEST_FUNC[test_type]()
                multicast_sock.sendto(result.encode(), (proxy_addr, proxy_port))
            except Exception as e:  
                logging.info(e)
                multicast_sock.sendto(str(e).encode(), (proxy_addr, proxy_port))

def main():
    host = os.environ.get('HOST', 'native')
    port = int(os.environ.get('PORT', '8080'))
    multicast_group = os.environ.get('MULTICAST_GROUP', '224.0.0.1')
    multicast_port = int(os.environ.get('MULTICAST_PORT', '8194'))
    proxy_addr = os.environ.get('PROXY_ADDR', 'proxy')
    proxy_port = int(os.environ.get('PROXY_PORT', '8080'))
    test_type = int(os.environ.get('TYPE', '0'))
    
    ut = threading.Thread(target=unicast_listen, args=(host, port, proxy_addr, proxy_port, test_type))
    mt = threading.Thread(target=multicast_listen, args=(multicast_group, multicast_port, proxy_addr, proxy_port, test_type))

    ut.start()
    mt.start()
    ut.join()
    mt.join()

if __name__ == '__main__':
    main()
