import socket

TYPES = ['native', 'xml', 'json', 'protobuf', 'avro', 'yaml', 'msgpack', 'all']

def main():
    proxy_addr = '0.0.0.0'
    proxy_port = 8080
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        for t in TYPES:
            try:
                print(f'get_result {t}:')
                s.sendto(f'get_result {t}'.encode(), (proxy_addr, proxy_port))
                res, _ = s.recvfrom(1024)
                print(res.decode())
            except Exception as e:
                print(e)


if __name__ == '__main__':
    main()
