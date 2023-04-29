import socket
import os
import logging
logging.basicConfig(level=logging.INFO)

TYPES = ['native', 'xml', 'json', 'protobuf', 'avro', 'yaml', 'msgpack', 'all']

def main():
    host = os.environ.get('HOST', 'proxy')
    port = int(os.environ.get('PORT', '8080'))
    service_port = int(os.environ.get('SERVICE_PORT', '8080'))
    multicast_group = os.environ.get('MULTICAST_GROUP', '224.0.0.1')
    multicast_port = int(os.environ.get('MULTICAST_PORT', '8194'))
    logging.info(f'listening on {host}:{port}')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((host, port))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        while True:
            data, addr = s.recvfrom(1024)
            logging.info(f'Got request {data} from {addr}')
            try:
                d = data.decode().strip('\n')
                d_split = d.split(' ')
                if len(d_split) == 2 and d_split[0] == 'get_result' and d_split[1] in TYPES:
                    if d_split[1] == 'all':
                        logging.info(f'sending {d} to {multicast_group}:{multicast_port}')
                        s.sendto(d.encode(), (multicast_group, multicast_port))
                        res = b''
                        for _ in range(len(TYPES) - 1):
                            r, r_addr = s.recvfrom(1024)
                            logging.info(f'Got response {r} from {r_addr}')
                            res += r + b'\n'
                        s.sendto(res, addr)
                    else:
                        logging.info(f'sending {d} to {d_split[1]}:{service_port}')
                        s.sendto(d.encode(), (d_split[1], service_port))
                        res, _ = s.recvfrom(1024)
                        s.sendto(res + b'\n', addr)
                else:
                    hint = '/'.join(TYPES)
                    s.sendto(f'Unknown command {d}, use get_result [{hint}]\n'.encode(), addr)
            except Exception as e:
                print(e)
    

if __name__ == '__main__':
    main()
